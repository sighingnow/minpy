import functools
import operator

import mxnet.symbol

import minpy.array
import minpy.numpy
import minpy.nn.layers
import minpy.nn.model_builder


class Identity(minpy.nn.model_builder.Layer):
    _module_name = 'identity'
    def __init__(self, name=None):
        super(Identity, self).__init__(name)

    def forward(self, X):
        return X


class ReLU(minpy.nn.model_builder.Layer):
    _module_name = 'ReLU'
    def __init__(self, name=None):
        """ Rectified linear unit.
        """
        super(ReLU, self).__init__(name=name)

    def forward(self, X, *args):
        return minpy.nn.layers.relu(X)


class Dropout(minpy.nn.model_builder.Layer):
    _module_name = 'dropout'
    def __init__(self, p):
        """ Dropout layer

        param p: probability of deactivating a neuron
        """

        super(Dropout, self).__init__()
        self._p = p

    def forward(self, data):
        return layers.dropout(data, self._p)


class Logistic(minpy.nn.model_builder.Layer):
    def __init__(self):
        """ Logistic function.
        """

        super(Sigmoid, self).__init__()

    def forward(self, X, *args):
        return 1 / (1 + np.exp(-X))


class Tanh(minpy.nn.model_builder.Layer):
    def __init__(self):
        """ Hyperbolic tangent function.
        """

        super(Tanh, self).__init__()

    def forward(self, X, *args):
        return np.tanh(X)


class Reshape(minpy.nn.model_builder.Layer):
    _module_name = 'reshape'
    def __init__(self, shape):
        """ Reshape.
        """

        super(Reshape, self).__init__()
        self._shape = shape

    def forward(self, X, *args):
        return minpy.numpy.reshape(X, self._shape)


class BatchReshape(minpy.nn.model_builder.Layer):
    _module_name = 'batch_reshape'
    def __init__(self, shape):
        """ Batch reshape.
        """

        super(Reshape, self).__init__()
        self._shape = shape

    def forward(self, X, *args):
        return minpy.numpy.reshape(X, X.shape[:1] + self._shape)


class Flatten(minpy.nn.model_builder.Layer):
    _module_name = 'flatten'
    def __init__(self):
        """ Flatten.
        """

        super(Flatten, self).__init__()

    def forward(self, X):
        return minpy.numpy.flatten(X)


class BatchFlatten(minpy.nn.model_builder.Layer):
    _module_name = 'flatten'
    def __init__(self):
        """ Flatten.
        """

        super(Flatten, self).__init__()

    def forward(self, X):
        N = X.shape[0]
        D = functools.reduce(operator.mul, X.shape[1:], 1)
        return minpy.numpy.reshape(X, (N, D))


# TODO use it
_get_shapes = lambda arrays : map(lambda array : array.shape, arrays)


class Symbolic(minpy.nn.model_builder.Layer):
    _module_name = 'symbolic'
    def __init__(self, symbol, variables=None, init_configs=None, update_configs=None, name=None):
        self._symbol = symbol

        params = set(symbol.list_arguments())
        self._variables = ('data',) if variables is None else variables
        params = params.difference(set(self._variables))
        params = tuple(params)
        aux_params = tuple(symbol.list_auxiliary_states())

        super(Symbolic, self).__init__(params, aux_params, name)

        self._func = None
        
    def forward(self, **kwargs):
        # kwargs should contain ALL variables
        if self._func is None:
            shapes = {key : value.shape for key, value in kwargs.items()}
            shapes.update(dict(zip(
                self._module_param_names,
                _get_shapes(self._get_params(*self._param_names))
            )))
            shapes.update(dict(zip(
                self._module_aux_param_names,
                _get_shapes(self._get_aux_params(*self._aux_param_names))
            )))
            self._func = minpy.core.Function(self._symbol, shapes)

        kwargs.update(dict(zip(self._module_param_names, self._get_params(*self._param_names))))
        kwargs.update(dict(zip(self._module_aux_param_names, self._get_aux_params(*self._aux_param_names))))

        self._func.is_train = self._mode == 'training'

        # returns multiple outputs (a tuple) for symbols yielding multiple outputs
        return self._func(**kwargs)

    def param_shapes(self, **kwargs):
        args = self._symbol.list_arguments()
        shapes, _, _ = self._symbol.infer_shape(**kwargs)
        shapes = dict(zip(args, tuple(shapes)))
        for variable in self._variables:
            del shapes[variable]
        local_to_global = dict(zip(self._module_param_names, self._param_names))
        shapes = {local_to_global[name] : shape for name, shape in shapes.items()}
        return shapes

    def aux_param_shapes(self, **kwargs):
        _, _, shapes = self._symbol.infer_shape(**kwargs)
        return dict(zip(self._aux_param_names, tuple(shapes)))


class FullyConnected(Symbolic):
    # TODO support providing weight as input
    def __init__(self, *args, **kwargs):
        name = kwargs.get('name', None)

        data = mxnet.symbol.Variable('data')
        fully_connected = mxnet.symbol.FullyConnected(data, *args, **kwargs)

        super(FullyConnected, self).__init__(fully_connected)

        init_configs = kwargs.get('init_configs', None)
        self._register_init_configs(init_configs)
        update_configs = kwargs.get('update_configs', None)
        self._register_update_configs(update_configs)

    def forward(self, data):
        return super(FullyConnected, self).forward(data=data)

    def param_shapes(self, input_shape):
        return super(FullyConnected, self).param_shapes(data=input_shape)

    def aux_param_shapes(self, input_shape):
        return {}


class Convolution(Symbolic):
    def __init__(self, *args, **kwargs):
        # TODO interface (currently mxnet)
        # TODO input weight/bias not supported currently
        # TODO name consistency with mxnet (for loading pre-trained mxnet model)

        name = kwargs.get('name', None)

        data = mxnet.symbol.Variable('data')
        convolution = mxnet.symbol.Convolution(data, *args, **kwargs)

        super(Convolution, self).__init__(convolution)

        init_configs = kwargs.get('init_configs', None)
        self._register_init_configs(init_configs)
        update_configs = kwargs.get('update_configs', None)
        self._register_update_configs(update_configs)

    def forward(self, data):
        return super(Convolution, self).forward(data=data)

    def param_shapes(self, input_shape):
        return super(Convolution, self).param_shapes(data=input_shape)

    def aux_param_shapes(self, input_shape):
        return {}


class Pooling(Symbolic):
    def __init__(self, *args, **kwargs):
        name = kwargs.get('name', None)

        data = mxnet.symbol.Variable('data')
        pooling = mxnet.symbol.Pooling(data, *args, **kwargs)

        super(Pooling, self).__init__(pooling)

    def forward(self, data):
        return super(Pooling, self).forward(data=data)

    def param_shapes(self, input_shape):
        return {}

    def aux_param_shapes(self, input_shape):
        return {}


class BatchNorm(Symbolic):
    # TODO training/inference mode
    def __init__(self, *args, **kwargs):
        name = kwargs.get('name', None)

        data = mxnet.symbol.Variable('data')
        batch_norm = mxnet.symbol.BatchNorm(data, *args, **kwargs)

        super(BatchNorm, self).__init__(batch_norm)

        # TODO merge into __init__
        init_configs = kwargs.get('init_configs', None)
        update_configs = kwargs.get('update_configs', None)

    def forward(self, data):
        return super(BatchNorm, self).forward(data=data)

    def param_shapes(self, input_shape):
        return super(BatchNorm, self).param_shapes(data=input_shape)

    def aux_param_shapes(self, input_shape):
        return super(BatchNorm, self).aux_param_shapes(data=input_shape)


class RNN(Symbolic):
    # TODO bidirectional
    def __init__(self, num_hidden, act_type):
        data = mxnet.symbol.Variable('data')
        hidden = mxnet.symbol.Variable('hidden')
        data = mxnet.symbol.FullyConnected(data=data, num_hidden=num_hidden, no_bias=True)
        hidden = mxnet.symbol.FullyConnected(hidden=hidden, num_hidden=num_hidden)
        network = mxnet.symbol.Activation(data + hidden, act_type=act_type)

        super(RNN, self).__init__(network)
        
        # TODO default_init_configs
    
    def forward(self, data, hidden):
        return super(RNN, self).forward(data=data, hidden=hidden)

    def param_shapes(self, data_shape, hidden_shape):
        return super(RNN, self).param_shapes(data=input_shape, hidden=hidden_shape)

    def aux_param_shapes(self, input_shape):
        return {}


class LSTM(Symbolic):
    def __init__(self, num_hidden, act_type):
        data = mxnet.symbol.Variable('data')
        hidden = mxnet.symbol.Variable('hidden')
        data = mxnet.symbol.FullyConnected(data=data, num_hidden=4 * num_hidden, no_bias=True)
        hidden = mxnet.symbol.FullyConnected(hidden=hidden, num_hidden=4 * num_hidden)
        network = data + hidden

        sliced = mxnet.symbol.SliceChannel(data=network, num_outputs=4, axis=1)
        i = mxnet.symbol.Activation(sliced[0], act_type='sigmoid')
        f = mxnet.symbol.Activation(sliced[1], act_type='sigmoid')
        o = mxnet.symbol.Activation(sliced[2], act_type='sigmoid')
        g = mxnet.symbol.Activation(sliced[3], act_type='tanh')

        cell = Variable('cell')
        next_cell = f * cell + i * g
        next_hidden = o * mxnet.symbol.Activation(next_ceil, act_type='tanh')
        symbol = mxnet.symbol.Group((next_hidden, next_cell))

        super(LSTM, self).__init__(symbol)
        
        # TODO default_init_configs
    
    def forward(self, data, hidden, cell):
        return super(LSTM, self).forward(data=data, hidden=hidden, cell=cell)

    def param_shapes(self, data_shape, hidden_shape, cell_shape):
        return super(LSTM, self).param_shapes(data=input_shape, hidden=hidden_shape, cell=cell_shape)

    def aux_param_shapes(self, input_shape):
        return {}