#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2016 romancpodolski <romancpodolski@Romans-MacBook-Pro.local>
#
# Distributed under terms of the MIT license.

from __future__ import print_function

import six.moves.cPickle as pickle
import gzip
import os
import sys
import timeit

sys.path.append(os.path.join(os.path.split(__file__)[0], '..', 'data'))

from data import load_data

import numpy as np

import theano
import theano.tensor as T

import climin as cli
import climin.initialize as init
import climin.util
import itertools

import matplotlib.pyplot as plt

class LogisticRegression(object):
    """Multi-class Logistic Regression Class

    The logistic regression is fully described by a weight matrix :math:`W`
    and bias vector :math:`b`. Classification is done by projecting data
    points onto a set of hyperplanes, the distance to which is used to
    determine a class membership probability.
    """

    def __init__(self, input, n_in, n_out, W = None, b = None):
        """ Initialize the parameters of the logistic regression

        :type input: theano.tensor.TensorType
        :param input: symbolic variable that describes the input of the
                      architecture (one minibatch)

        :type n_in: int
        :param n_in: number of input units, the dimension of the space in
                     which the datapoints lie

        :type n_out: int
        :param n_out: number of output units, the dimension of the space in
                      which the labels lie

        """
        # start-snippet-1
        # initialize with 0 the weights W as a matrix of shape (n_in, n_out)
        if W is None:
            W_values = np.zeros((n_in, n_out), dtype = theano.config.floatX)
            W = theano.shared(value = W_values, name = 'W', borrow = True )

        if b is None:
            b_values = np.zeros((n_out,), dtype = theano.config.floatX)
            b = theano.shared(value = b_values, name = 'b', borrow = True )

        self.W = W
        self.b = b

        # symbolic expression for computing the matrix of class-membership
        # probabilities
        # Where:
        # W is a matrix where column-k represent the separation hyperplane for
        # class-k
        # x is a matrix where row-j  represents input training sample-j
        # b is a vector where element-k represent the free parameter of
        # hyperplane-k
        self.p_y_given_x = T.nnet.softmax(T.dot(input, self.W) + self.b)

        # symbolic description of how to compute prediction as class whose
        # probability is maximal
        self.y_pred = T.argmax(self.p_y_given_x, axis=1)
        # end-snippet-1

        # parameters of the model
        self.params = [self.W, self.b]

        # keep track of model input
        self.input = input

    def negative_log_likelihood(self, y):
        """Return the mean of the negative log-likelihood of the prediction
        of this model under a given target distribution.

        .. math::

            \frac{1}{|\mathcal{D}|} \mathcal{L} (\theta=\{W,b\}, \mathcal{D}) =
            \frac{1}{|\mathcal{D}|} \sum_{i=0}^{|\mathcal{D}|}
                \log(P(Y=y^{(i)}|x^{(i)}, W,b)) \\
            \ell (\theta=\{W,b\}, \mathcal{D})

        :type y: theano.tensor.TensorType
        :param y: corresponds to a vector that gives for each example the
                  correct label

        Note: we use the mean instead of the sum so that
              the learning rate is less dependent on the batch size
        """
        # start-snippet-2
        # y.shape[0] is (symbolically) the number of rows in y, i.e.,
        # number of examples (call it n) in the minibatch
        # T.arange(y.shape[0]) is a symbolic vector which will contain
        # [0,1,2,... n-1] T.log(self.p_y_given_x) is a matrix of
        # Log-Probabilities (call it LP) with one row per example and
        # one column per class LP[T.arange(y.shape[0]),y] is a vector
        # v containing [LP[0,y[0]], LP[1,y[1]], LP[2,y[2]], ...,
        # LP[n-1,y[n-1]]] and T.mean(LP[T.arange(y.shape[0]),y]) is
        # the mean (across minibatch examples) of the elements in v,
        # i.e., the mean log-likelihood across the minibatch.
        return -T.mean(T.log(self.p_y_given_x)[T.arange(y.shape[0]), y])
        # end-snippet-2

    def errors(self, y):
        """Return a float representing the number of errors in the minibatch
        over the total number of examples of the minibatch ; zero one
        loss over the size of the minibatch

        :type y: theano.tensor.TensorType
        :param y: corresponds to a vector that gives for each example the
                  correct label
        """

        # check if y has same dimension of y_pred
        if y.ndim != self.y_pred.ndim:
            raise TypeError(
                'y should have the same shape as self.y_pred',
                ('y', y.type, 'y_pred', self.y_pred.type)
            )
        # check if y is of the correct datatype
        if y.dtype.startswith('int'):
            # the T.neq operator returns a vector of 0s and 1s, where 1
            # represents a mistake in prediction
            return T.mean(T.neq(self.y_pred, y))
        else:
            raise NotImplementedError()

def sgd_optimization_mnist(learning_rate=0.13, n_epochs=1000, dataset='mnist.pkl.gz', batch_size=600, optimizer='gd'):

    datasets = load_data(dataset, shared = False)

    train_set_x, train_set_y = datasets[0]
    valid_set_x, valid_set_y = datasets[1]
    test_set_x, test_set_y = datasets[2]

    tmpl = [(28 * 28, 10), 10]
    flat, (Weights, bias) = cli.util.empty_with_views(tmpl)

    cli.initialize.randomize_normal(flat, 0, 0.1) # initialize the parameters with random numbers

    if batch_size is None:
        args = itertools.repeat(([train_set_x, train_set_y], {}))
        batches_per_pass = 1
    else:
        args = cli.util.iter_minibatches([train_set_x, train_set_y], batch_size, [0, 0])
        args = ((i, {}) for i in args)
        n_train_batches = train_set_x.shape[0] // batch_size
        n_valid_batches = valid_set_x.shape[0] // batch_size
        n_test_batches  = test_set_x.shape[0] // batch_size

    print('... building the model')

    x = T.matrix('x') # data, represented as rasterized images dimension 28 * 28
    y = T.ivector('y') # labes, represented as 1D vector of [int] labels dimension 10

    classifier = LogisticRegression(
            input = x,
            n_in = 28 * 28,
            n_out = 10,
            W = theano.shared(value = Weights, name = 'W', borrow = True),
            b = theano.shared(value = bias, name = 'b', borrow = True)
            )

    cost = theano.function(
            inputs = [ x, y ],
            outputs = classifier.negative_log_likelihood(y),
            allow_input_downcast = True
            )

    gradients = theano.function(
            inputs = [x, y],
            outputs = [
                T.grad(classifier.negative_log_likelihood(y), classifier.W),
                T.grad(classifier.negative_log_likelihood(y), classifier.b)
                ],
            allow_input_downcast = True
            )

    def loss(parameters, inputs, targets):
        Weights, bias = cli.util.shaped_from_flat(parameters, tmpl)

        return cost(inputs, targets)

    def d_loss_wrt_pars(parameters, inputs, targets):
        Weights, bias = cli.util.shaped_from_flat(parameters, tmpl)

        g_W, g_b = gradients(inputs, targets)

        return np.concatenate([g_W.flatten(), g_b])

    zero_one_loss = theano.function(
            inputs = [x, y],
            outputs = classifier.errors(y),
            allow_input_downcast = True
            )

    if optimizer == 'gd':
        print('... using gradient descent')
        opt = cli.GradientDescent(flat, d_loss_wrt_pars, step_rate=0.1, momentum=.95, args=args)
    elif optimizer == 'bfgs':
        print('... using using quasi-newton BFGS')
        opt = cli.Bfgs(flat, loss, d_loss_wrt_pars, args=args)
    elif optimizer == 'lbfgs':
        print('... using using quasi-newton L-BFGS')
        opt = cli.Lbfgs(flat, loss, d_loss_wrt_pars, args=args)
    elif optimizer == 'nlcg':
        print('... using using non linear conjugate gradient')
        opt = cli.NonlinearConjugateGradient(flat, loss, d_loss_wrt_pars, args=args)
    elif optimizer == 'rmsprop':
        print('... using rmsprop')
        opt = cli.RmsProp(flat, d_loss_wrt_pars, step_rate=1e-4, decay=0.9, args=args)
    elif optimizer == 'rprop':
        print('... using resilient propagation')
        opt = cli.Rprop(flat, d_loss_wrt_pars, args=args)
    elif optimizer == 'adam':
        print('... using adaptive momentum estimation optimizer')
        opt = cli.Adam(flat, d_loss_wrt_pars, step_rate = 0.0002, decay = 0.99999999, decay_mom1 = 0.1, decay_mom2 = 0.001, momentum = 0, offset = 1e-08, args=args)
    elif optimizer == 'adadelta':
        print('... using adadelta')
        opt = cli.Adadelta(flat, d_loss_wrt_pars, step_rate=1, decay = 0.9, momentum = .95, offset = 0.0001, args=args)
    else:
        print('unknown optimizer')
        return 1

    print('... training the model')

    # early stopping parameters
    patience = 5000 # look at this many samples regardless
    patience_increase = 2 # wait this mutch longer when a new best is found
    improvement_threshold = 0.995 # a relative improvement of this mutch is considered signigicant
    validation_frequency = min(n_train_batches, patience // 2)
    best_validation_loss = np.inf
    test_loss = 0.

    valid_losses = []
    train_losses = []
    test_losses = []

    done_looping = False
    epoch = 0 # do I need this parameter?

    start_time = timeit.default_timer()
    for info in opt:
        iter = info['n_iter']
        epoch = iter // n_train_batches + 1
        minibatch_index = iter % n_train_batches
        minibatch_x, minibatch_y = info['args']

        if ( iter + 1 ) % validation_frequency == 0:
            # compute zero-one loss on validation set
            validation_loss = zero_one_loss(valid_set_x, valid_set_y)
            valid_losses.append([epoch, validation_loss])
            # train_losses.append(zero_one_loss(train_set_x, train_set_y))

            print(
                    'epoch %i, minibatch %i/%i, validation error % f %%' %
                    (
                        epoch,
                        minibatch_index + 1,
                        n_train_batches,
                        validation_loss * 100
                        )
                    )
            # if we got the best validation score until now
            if validation_loss < best_validation_loss:
               # improve patience if loss improvement is good enough
                if validation_loss < best_validation_loss * improvement_threshold:
                    patience = max(patience, iter * patience_increase)
                best_validation_loss = validation_loss
                # test it on the test set
                test_loss = zero_one_loss(test_set_x, test_set_y)
                test_losses.append([epoch, test_loss])

                print(
                        '    epoch %i, minibatch %i/%i, test error of best model %f %%' %
                        (
                            epoch,
                            minibatch_index + 1,
                            n_train_batches,
                            test_loss * 100
                            )
                        )

                with open('best_model_logreg_'+optimizer+'.pkl', 'wb') as f:
                    pickle.dump(classifier, f)

        if patience <= iter or epoch >= n_epochs:
            break

    end_time = timeit.default_timer()

    print('Optimization complete with best validation score of %f %%, with test performance %f %%' % (best_validation_loss * 100., test_loss * 100.))
    print('The code run for %d epochs, with %f epochs/sec' % (epoch, 1. * epoch / (end_time - start_time)))
    print(('The code for file ' + os.path.split(__file__)[1] + ' ran for %.1fs' % ((end_time - start_time))), file=sys.stderr)

    losses = (np.asarray(train_losses), np.asarray(valid_losses), np.asarray(test_losses))
    methadata = (best_validation_loss * 100., test_loss * 100., epoch, 1. * epoch / (end_time - start_time), end_time - start_time)

    return classifier, losses, methadata 

def predict():
    """
    An example of how to load a trained model and use it
    to predict labels.
    """

    # loads the saved model
    classifier = pickle.load(open('best_model.pkl'))

    # compile a predictor function
    predict_model = theano.function(
            inputs = [classifier.input],
            outputs = classifier.y_pred)

    # We can test it on some examples from test set
    dataset = 'mnist.pkl.gz'
    datasets = load_data(dataset)
    test_set_x, test_set_y = datasets[2]
    test_set_x = test_set_x.get_value()

    predicted_values = predict_model(test_set_x[:10])
    print("Predicted values for the first 10 examples in test set:")
    print(predicted_values)

if __name__ == "__main__":
    optimizer_names = {
            'gd': 'Gradient Descent',
            'bfgs': 'Quasi-Newton BFGS',
            'lbfgs': 'Quasi-Newton L-BFGS',
            'nlcg': 'Non-Linear Conjugate Gradient',
            'rmsprop': 'RMSPROP',
            'rprop': 'Resilient Propagation',
            'adam': 'Adam',
            'adadelta': 'Adadelta',
            }

    for o in ['gd', 'bfgs', 'lbfgs', 'nlcg', 'rmsprop', 'rprop', 'adam', 'adadelta']:
    # for o in ['gd', 'rmsprop', 'rprop', 'adam', 'adadelta']:

        f_error = plt.figure()
        classifier, losses, methadata = sgd_optimization_mnist(n_epochs = 1000, optimizer=o)
        train_loss, valid_loss, test_loss = losses
        best_validation_loss, best_test_loss, epochs, epochs_pro_second, time_trained = methadata

        plt.plot(valid_loss[:,0], valid_loss[:,1], '-', linewidth = 1, label = 'validation loss')
        plt.plot(test_loss[:,0], test_loss[:,1], '-', linewidth = 1, label = 'test loss')

        plt.legend()

        plt.title('Error ' + optimizer_names[o] + " with best validation score of %f %%,\n test performance %f %%, after %.1fs " % (best_validation_loss, best_test_loss, time_trained))
        plt.savefig('errors_'+o+'.png')

        f_repfields, axes = plt.subplots(2, 5, subplot_kw = {'xticks': [], 'yticks': []})
        f_repfields.subplots_adjust(hspace = 0.3, wspace = 0.05)
        f_repfields.canvas.set_window_title('Receptive Fields for Logistic Regression')

        repfield = []
        for i in range(10):
            repfield.append(np.reshape(np.array(classifier.W.get_value())[:,i], (28, 28)))

        i = 0
        for ax, rep in zip(axes.flat, repfield):
            ax.imshow(rep, cmap=plt.cm.gray, interpolation = 'none')
            ax.set_title('Weights ' + str(i))
            i = i + 1

        f_repfields.subplots_adjust(hspace=0.03, wspace=0.05)

        f_repfields.suptitle('Receptive Fields for Logisitc Regression with ' + optimizer_names[o] + ' on MNIST')
        plt.savefig('repfields_'+o+'.png')
