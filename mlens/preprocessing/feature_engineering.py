"""ML-ENSEMBLE

:author: Sebastian Flennerhag
:licence: MIT

Class for generating new features in the form of predictions from a given set
of models. Prediction are generated using KFold out-of-sample predictions.
"""

from __future__ import division, print_function

from pandas import DataFrame, concat
from numpy import hstack
from sklearn.base import BaseEstimator, TransformerMixin
from mlens.base import name_estimators, IdTrain, check_instances
from mlens.base import clone_base_estimators
from mlens.base import check_fit_overlap
from mlens.utils import print_time
from mlens.parallel import preprocess_folds, fit_estimators, base_predict
from mlens.externals import six
from time import time
import sys


class PredictionFeature(BaseEstimator, TransformerMixin):

    """Prediction Feature.

    Transformer that appends columns of predictions from a set of estimators
    to a matrix.

    Parameters
    ----------
    estimators : list
        estimators to use for generating predictions. One feature of
        predictions is generated per estimator.

    folds : int, obj (default = 2)
        number of folds to use for constructing prediction feature set.
        Either pass a KFold class object that accepts as ``split`` method,
        or the number of folds in Scikit-learn ``KFold`` instance.

    shuffle : bool (default = True)
        whether to shuffle data for creating k-fold out of sample predictions.

    random_state : int, (default = None)
        seed for creating folds during fitting (if ``shuffle = True``).

    sample_size : int
        subset size to sample from training set for check during ``transform``
        call. Data sets with low variation need larger subsets to ensure
        the subset is unique.

    verbose : int or bool (default = False)
        level of verbosity.

            - ``verbose = 0`` silent (same as ``verbose = False``)
            - ``verbose = 1`` messages at start and finish \
            (same as ``verbose = True``)
            - ``verbose = 2`` messages for each layer

        If ``verbose >= 50`` prints to ``sys.stdout``, else ``sys.stderr``.
        For verbosity in the layers themselves, use ``fit_params``.

    n_jobs : int (default = -1)
        number of CPU cores to use for fitting and prediction.

    Attributes
    ----------
    estimators\_ : list
        list of fitted estimator.
    """

    def __init__(self, estimators, folds=2, shuffle=True, scorer=None,
                 concat=True, random_state=None, sample_size=10,
                 verbose=False, n_jobs=1):

        self.estimators = estimators
        self.named_estimators = name_estimators(estimators)

        self.folds = folds
        self.shuffle = shuffle
        self.scorer = scorer
        self.concat = concat
        self.random_state = random_state
        self.sample_size = sample_size
        self.check = IdTrain(self.sample_size)
        self.verbose = verbose
        self.n_jobs = n_jobs

    def fit(self, X, y):
        """Fit estimators.

        Parameters
        ----------
        X : array-like, shape=[n_samples, n_features]
            input data to fit estimators on.

        y : array-like, shape=[n_samples, ]
            training labels.

        Returns
        -------
        self : instance
            class instance with fitted estimators.
        """
        # Store training set id
        self.check = self.check.fit(X)

        if self.verbose > 0:
            printout = sys.stdout if self.verbose > 50 else sys.stderr
            print('Fitting estimators\n', file=printout)
            printout.flush()
            ts = time()
        else:
            printout = None

        # Fit estimators for training set
        Min = preprocess_folds(None, X, y, folds=self.folds, fit=False,
                               shuffle=self.shuffle,
                               random_state=self.random_state,
                               n_jobs=self.n_jobs, verbose=self.verbose)

        # >> Generate mapping between folds and estimators
        Min = [tup[:-1] + [i] for i, tup in enumerate(Min)]
        ests_ = {i: clone_base_estimators(check_instances(self.estimators))['']
                 for i in range(len(Min))}
        self.train_ests_ = fit_estimators(Min, ests_, None,
                                          self.n_jobs, self.verbose)

        # Fit estimators for test set
        self.test_ests_ = \
            fit_estimators([[X, '']],
                           clone_base_estimators(check_instances(
                                   self.estimators)),
                           y, self.n_jobs, self.verbose)

        fitted_test_ests = [est_name for est_name, _ in self.test_ests_['']]
        self._fitted_ests = fitted_test_ests

        if self.verbose > 0:
            print_time(ts, 'Fit complete', file=printout)

        return self

    def predict(self, X, y=None):
        """Predict with fitted ensemble.

        Parameters
        ----------
        X : array-like, shape=[n_samples, n_features]
            Data to use for making predictions.

        Returns
        -------
        X_pred : array-like, shape=[n_samples, n_estimators]
            prediction matrix.
        """
        as_df = isinstance(X, DataFrame)

        if self.check.is_train(X):
            # Use cv folds to generate predictions
            Min = preprocess_folds(None, X, y, folds=self.folds, fit=False,
                                   shuffle=self.shuffle,
                                   random_state=self.random_state,
                                   n_jobs=self.n_jobs, verbose=self.verbose)

            Min = [tup[:-1] + [i] for i, tup in enumerate(Min)]
            folded_preds = True
            estimators = self.train_ests_
            function_args = (False, False)
        else:
            # Predict using estimators fitted on full training data
            Min = [[X, '']]
            folded_preds = False
            estimators = self.test_ests_
            function_args = (False,)

        # Generate predictions matrix
        M, fitted_estimator_names = \
            base_predict(Min, estimators, n=X.shape[0],
                         folded_preds=folded_preds,
                         function_args=function_args,
                         columns=self._fitted_ests, as_df=as_df,
                         n_jobs=self.n_jobs, verbose=self.verbose)

        check_fit_overlap(self._fitted_ests, fitted_estimator_names,
                          'prediction_feature')
        return M

    def transform(self, X, y=None):
        """Transform input array X by concatenating prediction features.

        Parameters
        ----------
        X : array-like, shape=[n_samples, n_features]
            input data.

        Returns
        -------
        X_concat : array-like, shape=[n_samples, n_features + n_estimators]
            Full matrix X concatenated by ``n_estimators`` prediction features.
        """
        M = self.predict(X, y)

        if not self.concat:
            return M

        if isinstance(X, DataFrame):
            # Avoid pulling out the underlying ndarray in case it's sparse
            M.set_index(X.index, inplace=True)
            return concat((X, M), 1)
        else:
            return hstack((X, M))

    def get_params(self, deep=True):
        """Get parameters of the PredictionFeature transformer."""
        if not deep:
            return super(PredictionFeature, self).get_params(deep=False)
        else:
            out = {'folds': self.folds,
                   'shuffle': self.shuffle,
                   'random_state': self.random_state,
                   'sample_size': self.check.size,
                   'verbose': self.verbose,
                   'n_jobs': self.n_jobs,
                   'scorer': self.scorer,
                   'concat': self.concat}

            out.update(self.named_estimators.copy())
            for name, step in six.iteritems(self.named_estimators):
                for key, value in six.iteritems(step.get_params(deep=True)):
                    out['%s__%s' % (name, key)] = value
            return out
