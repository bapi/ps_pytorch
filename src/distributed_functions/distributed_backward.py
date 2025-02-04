import torch
import warnings

from torch.autograd import Variable
from torch.autograd.function import Function, NestedIOFunction
# from torch.autograd.stochastic_function import StochasticFunction
from torch.autograd.gradcheck import gradcheck


def _make_grads(outputs, grads, user_create_graph):
    if user_create_graph is not None:
        create_graph = user_create_graph
    else:
        create_graph = any(isinstance(grad, Variable) and not grad.volatile
                           for grad in grads)

    new_grads = []
    for out, grad in zip(outputs, grads):
        if isinstance(grad, Variable):
            new_grads.append(grad)
        elif torch.is_tensor(grad):
            new_grads.append(Variable(grad, volatile=not create_graph))
        elif grad is None:
            if out.requires_grad:
                if out.numel() != 1:
                    raise RuntimeError("grad can be implicitly created only for scalar outputs")
                data = out.data
                new_grads.append(
                    Variable(data.new().resize_as_(data).fill_(1), volatile=not create_graph))
            else:
                new_grads.append(None)
        else:
            raise TypeError("gradients can be either Tensors, Variables or None, but got " +
                            type(grad).__name__)
    return tuple(new_grads), create_graph


def backward(variables, grad_variables=None, retain_graph=None, create_graph=None, retain_variables=None):
    """Computes the sum of gradients of given variables w.r.t. graph leaves.

    The graph is differentiated using the chain rule. If any of ``variables``
    are non-scalar (i.e. their data has more than one element) and require
    gradient, the function additionally requires specifying ``grad_variables``.
    It should be a sequence of matching length, that contains gradient of
    the differentiated function w.r.t. corresponding variables (``None`` is an
    acceptable value for all variables that don't need gradient tensors).

    This function accumulates gradients in the leaves - you might need to zero
    them before calling it.

    Arguments:
        variables (sequence of Variable): Variables of which the derivative will be
            computed.
        grad_variables (sequence of (Tensor, Variable or None)): Gradients w.r.t.
            each element of corresponding variables.  Any tensors will be
            automatically converted to Variables that are volatile unless
            ``create_graph`` is True.  None values can be specified for scalar
            Variables or ones that don't require grad. If a None value would
            be acceptable for all grad_variables, then this argument is optional.
        retain_graph (bool, optional): If False, the graph used to compute the grad
            will be freed. Note that in nearly all cases setting this option to True
            is not needed and often can be worked around in a much more efficient
            way. Defaults to the value of ``create_graph``.
        create_graph (bool, optional): If true, graph of the derivative will
            be constructed, allowing to compute higher order derivative products.
            Defaults to False, unless ``grad_variables`` contains at least one
            non-volatile Variable.
    """
    variables = (variables,) if isinstance(variables, Variable) else tuple(variables)

    if grad_variables is None:
        grad_variables = [None] * len(variables)
    elif isinstance(grad_variables, Variable) or torch.is_tensor(grad_variables):
        grad_variables = [grad_variables]
    else:
        grad_variables = list(grad_variables)

    grad_variables, create_graph = _make_grads(variables, grad_variables, create_graph)

    if retain_variables is not None:
        if retain_graph is not None:
            raise ValueError("only one of retain_graph and retain_variables can be specified")
        retain_graph = retain_variables
        warnings.warn("retain_variables option is deprecated and will be removed in 0.3. "
                      "Use retain_graph instead.")
    elif retain_graph is None:
        retain_graph = create_graph

    Variable._execution_engine.run_backward(
        variables, grad_variables, retain_graph)