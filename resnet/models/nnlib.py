from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import numpy as np
import tensorflow as tf

from resnet.utils import logger

log = logger.get()


def weight_variable(shape,
                    init_method=None,
                    dtype=tf.float32,
                    init_param=None,
                    wd=None,
                    name=None,
                    trainable=True):
  """Declares a variable.

    Args:
        shape: Shape of the weights, list of int.
        init_method: Initialization method, "constant" or "truncated_normal".
        init_param: Initialization parameters, dictionary.
        wd: Weight decay, float.
        name: Name of the variable, str.
        trainable: Whether the variable can be trained, bool.

    Returns:
        var: Declared variable.
    """
  if dtype != tf.float32:
    log.warning("Not using float32, currently using {}".format(dtype))
  if init_method is None:
    initializer = tf.zeros_initializer(shape, dtype=dtype)
  elif init_method == "truncated_normal":
    if "mean" not in init_param:
      mean = 0.0
    else:
      mean = init_param["mean"]
    if "stddev" not in init_param:
      stddev = 0.1
    else:
      stddev = init_param["stddev"]
    initializer = tf.truncated_normal_initializer(
        mean=mean, stddev=stddev, seed=1, dtype=dtype)
  elif init_method == "uniform_scaling":
    if "factor" not in init_param:
      factor = 1.0
    else:
      factor = init_param["factor"]
    initializer = tf.uniform_unit_scaling_initializer(
        factor=factor, seed=1, dtype=dtype)
  elif init_method == "constant":
    if "val" not in init_param:
      value = 0.0
    else:
      value = init_param["val"]
    initializer = tf.constant_initializer(value=value, dtype=dtype)
  elif init_method == "xavier":
    initializer = tf.contrib.layers.xavier_initializer(
        uniform=False, seed=1, dtype=dtype)
  else:
    raise ValueError("Non supported initialization method!")
  log.info("Weight shape {}".format(shape))
  if wd is not None:
    if wd > 0.0:
      reg = lambda x: tf.mul(tf.nn.l2_loss(x), wd)
      log.info("Weight decay {}".format(wd))
    else:
      log.warning("No weight decay")
      reg = None
  else:
    log.warning("No weight decay")
    reg = None
  with tf.device("/cpu:0"):
    var = tf.get_variable(
        name,
        shape,
        initializer=initializer,
        regularizer=reg,
        dtype=dtype,
        trainable=trainable)
  return var


def cnn(x,
        filter_size,
        strides,
        pool_fn,
        pool_size,
        pool_strides,
        act_fn,
        dtype=tf.float32,
        add_bias=True,
        wd=None,
        init_std=None,
        init_method=None,
        scope="cnn",
        trainable=True):
  """Builds a convolutional neural networks.
    Each layer contains the following operations:
        1) Convolution, y = w * x.
        2) Additive bias (optional), y = w * x + b.
        3) Activation function (optional), y = g( w * x + b ).
        4) Pooling (optional).

    Args:
        x: Input variable.
        filter_size: Shape of the convolutional filters, list of 4-d int.
        strides: Convolution strides, list of 4-d int.
        pool_fn: Pooling functions, list of N callable objects.
        pool_size: Pooling field size, list of 4-d int.
        pool_strides: Pooling strides, list of 4-d int.
        act_fn: Activation functions, list of N callable objects.
        add_bias: Whether adding bias or not, bool.
        wd: Weight decay, float.
        scope: Scope of the model, str.
    """
  num_layer = len(filter_size)
  h = x
  with tf.variable_scope(scope):
    for ii in range(num_layer):
      with tf.variable_scope("layer_{}".format(ii)):
        if init_method is not None and init_method[ii]:
          w = weight_variable(
              filter_size[ii],
              init_method=init_method[ii],
              dtype=dtype,
              init_param={"mean": 0.0,
                          "stddev": init_std[ii]},
              wd=wd,
              name="w",
              trainable=trainable)
        else:
          w = weight_variable(
              filter_size[ii],
              init_method="truncated_normal",
              dtype=dtype,
              init_param={"mean": 0.0,
                          "stddev": init_std[ii]},
              wd=wd,
              name="w",
              trainable=trainable)

        if add_bias:
          b = weight_variable(
              [filter_size[ii][3]],
              init_method="constant",
              dtype=dtype,
              init_param={"val": 0},
              # wd=wd,       ####### Change this back if it changes anything!!!
              name="b",
              trainable=trainable)
        h = tf.nn.conv2d(
            h, w, strides=strides[ii], padding="SAME", name="conv")
        if add_bias:
          h = tf.add(h, b, name="conv_bias")
        if act_fn[ii] is not None:
          h = act_fn[ii](h, name="act")
        if pool_fn[ii] is not None:
          h = pool_fn[ii](h,
                          pool_size[ii],
                          strides=pool_strides[ii],
                          padding="SAME",
                          name="pool")
  return h


def mlp(x,
        dims,
        is_training=True,
        act_fn=None,
        dtype=tf.float32,
        add_bias=True,
        wd=None,
        init_std=None,
        init_method=None,
        scope="mlp",
        dropout=None,
        trainable=True):
  """Builds a multi-layer perceptron.
    Each layer contains the following operations:
        1) Linear transformation, y = w^T x.
        2) Additive bias (optional), y = w^T x + b.
        3) Activation function (optional), y = g( w^T x + b )
        4) Dropout (optional)

    Args:
        x: Input variable.
        dims: Layer dimensions, list of N+1 int.
        act_fn: Activation functions, list of N callable objects.
        add_bias: Whether adding bias or not, bool.
        wd: Weight decay, float.
        scope: Scope of the model, str.
        dropout: Whether to apply dropout, None or list of N bool.
    """
  num_layer = len(dims) - 1
  h = x
  with tf.variable_scope(scope):
    for ii in range(num_layer):
      with tf.variable_scope("layer_{}".format(ii)):
        dim_in = dims[ii]
        dim_out = dims[ii + 1]

        if init_method is not None and init_method[ii]:
          w = weight_variable(
              [dim_in, dim_out],
              init_method=init_method[ii],
              dtype=dtype,
              init_param={"mean": 0.0,
                          "stddev": init_std[ii]},
              wd=wd,
              name="w",
              trainable=trainable)
        else:
          w = weight_variable(
              [dim_in, dim_out],
              init_method="truncated_normal",
              dtype=dtype,
              init_param={"mean": 0.0,
                          "stddev": init_std[ii]},
              wd=wd,
              name="w",
              trainable=trainable)

        if add_bias:
          b = weight_variable(
              [dim_out],
              init_method="constant",
              dtype=dtype,
              init_param={"val": 0.0},
              # wd=wd,       ####### Change this back if it changes anything!!!
              name="b",
              trainable=trainable)

        h = tf.matmul(h, w, name="linear")
        if add_bias:
          h = tf.add(h, b, name="linear_bias")
        if act_fn and act_fn[ii] is not None:
          h = act_fn[ii](h)
        if dropout is not None and dropout[ii]:
          log.info("Apply dropout 0.5")
          if is_training:
            keep_prob = 0.5
          else:
            keep_prob = 1.0
          h = tf.nn.dropout(h, keep_prob=keep_prob)
  return h


def batch_norm(x,
               n_out,
               is_training,
               reuse=None,
               gamma=None,
               beta=None,
               axes=[0, 1, 2],
               eps=1e-3,
               scope="bn",
               name="bn_out",
               return_mean=False):
  """Applies batch normalization.
    Collect mean and variances on x except the last dimension. And apply
    normalization as below:
        x_ = gamma * (x - mean) / sqrt(var + eps) + beta

    Args:
        x: Input tensor, [B, ...].
        n_out: Integer, depth of input variable.
        gamma: Scaling parameter.
        beta: Bias parameter.
        axes: Axes to collect statistics.
        eps: Denominator bias.
        return_mean: Whether to also return the computed mean.

    Returns:
        normed: Batch-normalized variable.
        mean: Mean used for normalization (optional).
    """
  with tf.variable_scope(scope, reuse=reuse):
    emean = tf.get_variable("ema_mean", [n_out], trainable=False)
    evar = tf.get_variable("ema_var", [n_out], trainable=False)
    if is_training:
      batch_mean, batch_var = tf.nn.moments(x, axes, name='moments')
      batch_mean.set_shape([n_out])
      batch_var.set_shape([n_out])
      ema = tf.train.ExponentialMovingAverage(decay=0.9)
      ema_apply_op_local = ema.apply([batch_mean, batch_var])
      with tf.control_dependencies([ema_apply_op_local]):
        mean, var = tf.identity(batch_mean), tf.identity(batch_var)
      emean_val = ema.average(batch_mean)
      evar_val = ema.average(batch_var)
      with tf.control_dependencies(
          [tf.assign(emean, emean_val), tf.assign(evar, evar_val)]):
        normed = tf.nn.batch_normalization(
            x, mean, var, beta, gamma, eps, name=name)
    else:
      normed = tf.nn.batch_normalization(
          x, emean, evar, beta, gamma, eps, name=name)
  if return_mean:
    if is_training:
      return normed, mean
    else:
      return normed, emean
  else:
    return normed


def batch_norm_mean_only(x,
                         n_out,
                         is_training,
                         reuse=None,
                         gamma=None,
                         beta=None,
                         axes=[0, 1, 2],
                         scope="bnms",
                         name="bnms_out",
                         return_mean=False):
  """Applies mean only batch normalization.
    Collect mean and variances on x except the last dimension. And apply
    normalization as below:
        x_ = gamma * (x - mean) + beta

    Args:
        x: Input tensor, [B, ...].
        n_out: Integer, depth of input variable.
        gamma: Scaling parameter.
        beta: Bias parameter.
        axes: Axes to collect statistics.
        eps: Denominator bias.
        return_mean: Whether to also return the computed mean.

    Returns:
        normed: Batch-normalized variable.
        mean: Mean used for normalization (optional).
    """
  with tf.variable_scope(scope, reuse=reuse):
    emean = tf.get_variable("ema_mean", [n_out], trainable=False)
    if is_training:
      batch_mean = tf.reduce_mean(x, axes)
      ema = tf.train.ExponentialMovingAverage(decay=0.9)
      ema_apply_op_local = ema.apply([batch_mean])
      with tf.control_dependencies([ema_apply_op_local]):
        mean = tf.identity(batch_mean)
      emean_val = ema.average(batch_mean)
      with tf.control_dependencies([tf.assign(emean, emean_val)]):
        normed = x - batch_mean
      if gamma is not None:
        normed *= gamma
      if beta is not None:
        normed += beta
    else:
      normed = x - emean
      if gamma is not None:
        normed *= gamma
      if beta is not None:
        normed += beta
  if return_mean:
    if is_training:
      return normed, mean
    else:
      return normed, emean
  else:
    return normed


def layer_norm(x,
               gamma=None,
               beta=None,
               axes=[1, 2, 3],
               eps=1e-3,
               scope="ln",
               name="ln_out",
               return_mean=False):
  """Applies layer normalization.
    Collect mean and variances on x except the first dimension. And apply
    normalization as below:
        x_ = gamma * (x - mean) / sqrt(var + eps)

    Args:
        x: Input tensor, [B, ...].
        axes: Axes to collect statistics.
        gamma: Scaling parameter.
        beta: Bias parameter.
        eps: Denominator bias.
        return_mean: Whether to also return the computed mean.

    Returns:
        normed: Layer-normalized variable.
        mean: Mean used for normalization (optional).
    """
  with tf.variable_scope(scope):
    x_shape = [x.get_shape()[-1]]
    mean, var = tf.nn.moments(x, axes, name='moments', keep_dims=True)
    normed = (x - mean) / tf.sqrt(eps + var)
    if gamma is not None:
      normed *= gamma
    if beta is not None:
      normed += beta
    normed = tf.identity(normed, name=name)
  if return_mean:
    return normed, mean
  else:
    return normed


def div_norm_2d(x,
                sum_window,
                sup_window,
                gamma=None,
                beta=None,
                eps=1.0,
                scope="dn",
                name="dn_out",
                return_mean=False):
  """Applies divisive normalization on CNN feature maps.
    Collect mean and variances on x on a local window across channels. And apply
    normalization as below:
        x_ = gamma * (x - mean) / sqrt(var + eps)

    Args:
        x: Input tensor, [B, H, W, C].
        sum_window: Summation window size, [H_sum, W_sum].
        sup_window: Suppression window size, [H_sup, W_sup].
        gamma: Scaling parameter.
        beta: Bias parameter.
        eps: Denominator bias.
        return_mean: Whether to also return the computed mean.

    Returns:
        normed: Divisive-normalized variable.
        mean: Mean used for normalization (optional).
    """
  with tf.variable_scope(scope):
    w_sum = tf.ones(sum_window + [1, 1]) / np.prod(np.array(sum_window))
    w_sup = tf.ones(sup_window + [1, 1]) / np.prod(np.array(sum_window))
    x_mean = tf.reduce_mean(x, [3], keep_dims=True)
    x_mean = tf.nn.conv2d(x_mean, w_sum, strides=[1, 1, 1, 1], padding='SAME')
    normed = x - x_mean
    x2 = tf.square(normed)
    x2_mean = tf.reduce_mean(x2, [3], keep_dims=True)
    x2_mean = tf.nn.conv2d(
        x2_mean, w_sup, strides=[1, 1, 1, 1], padding='SAME')
    denom = tf.sqrt(x2_mean + eps)
    normed = normed / denom
    if gamma is not None:
      normed *= gamma
    if beta is not None:
      normed += beta
    normed = tf.identity(normed, name=name)
  if return_mean:
    return normed, x_mean
  else:
    return normed


def div_norm_1d(x,
                sum_window,
                sup_window,
                gamma=None,
                beta=None,
                eps=1.0,
                scope='dn',
                name="dn_out",
                return_mean=False):
  """Applies divisive normalization on fully connected layers.
    Collect mean and variances on x on a local window. And apply
    normalization as below:
        x_ = gamma * (x - mean) / sqrt(var + eps)

    Args:
        x: Input tensor, [B, D].
        sum_window: Summation window size, W_sum.
        sup_window: Suppression window size, W_sup.
        gamma: Scaling parameter.
        beta: Bias parameter.
        eps: Denominator bias.
        return_mean: Whether to also return the computed mean.

    Returns:
        normed: Divisive-normalized variable.
        mean: Mean used for normalization (optional).
    """
  with tf.variable_scope(scope):
    x_shape = [x.get_shape()[-1]]
    x = tf.expand_dims(x, 2)
    w_sum = tf.ones([sum_window, 1, 1], dtype='float') / float(sum_window)
    w_sup = tf.ones([sup_window, 1, 1], dtype='float') / float(sup_window)
    mean = tf.nn.conv1d(x, w_sum, stride=1, padding='SAME')
    x_mean = x - mean
    x2 = tf.square(x_mean)
    var = tf.nn.conv1d(x2, w_sup, stride=1, padding='SAME')
    normed = (x - mean) / tf.sqrt(eps + var)
    normed = tf.squeeze(normed, [2])
    mean = tf.squeeze(mean, [2])
    if gamma is not None:
      normed *= gamma
    if beta is not None:
      normed += beta
    normed = tf.identity(normed, name=name)
  if return_mean:
    return normed, mean
  else:
    return normed