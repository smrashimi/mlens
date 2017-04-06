"""ML-ENSEMBLE

Test model selection.
"""
import numpy as np
from mlens.utils.dummy import Data, OLS, Scale
from mlens.metrics import rmse, make_scorer
from mlens.model_selection import Evaluator
from scipy.stats import randint


np.random.seed(100)

rmse_scorer = make_scorer(rmse, greater_is_better=False)

# Stack is nonsense here - we just need proba to be false
X, y = Data('stack', False, False).get_data((100, 2), 2)


def test_no_prep():
    """[Model Selection] Test run without preprocessing."""
    evl = Evaluator(rmse, cv=10, shuffle=False, n_jobs=1, random_state=100)
    evl.fit(X, y,
            estimators=[OLS()],
            param_dicts={'ols': {'offset': randint(1, 10)}},
            n_iter=3)

    np.testing.assert_approx_equal(
            evl.summary['test_score_mean']['ols'], 806.70651350960748)
    assert evl.summary['params']['ols']['offset'] == 4


def test_w_prep():
    """[Model Selection] Test run with preprocessing, double step."""
    evl = Evaluator(rmse, cv=10, shuffle=False, n_jobs=1, random_state=100)

    # Preprocessing
    evl.preprocess(X, y, {'pr': [Scale()], 'no': []})

    # Fitting
    evl.evaluate(X, y,
                 estimators=[OLS()],
                 param_dicts={'ols': {'offset': randint(1, 10)}},
                 n_iter=3)

    np.testing.assert_approx_equal(
            evl.summary['test_score_mean'][('no', 'ols')], 806.70651350960748)
    np.testing.assert_approx_equal(
            evl.summary['test_score_mean'][('pr', 'ols')], 509.01956468572143)

    assert evl.summary['params'][('no', 'ols')]['offset'] == 4
    assert evl.summary['params'][('pr', 'ols')]['offset'] == 4


def test_w_prep_fit():
    """[Model Selection] Test run with preprocessing, single step."""
    evl = Evaluator(rmse, cv=10, shuffle=False, n_jobs=1, random_state=100)

    evl.fit(X, y,
            estimators=[OLS()],
            param_dicts={'ols': {'offset': randint(1, 10)}},
            preprocessing={'pr': [Scale()], 'no': []},
            n_iter=3)

    np.testing.assert_approx_equal(
            evl.summary['test_score_mean'][('no', 'ols')], 806.70651350960748)
    np.testing.assert_approx_equal(
            evl.summary['test_score_mean'][('pr', 'ols')], 509.01956468572143)

    assert evl.summary['params'][('no', 'ols')]['offset'] == 4
    assert evl.summary['params'][('pr', 'ols')]['offset'] == 4


def test_w_prep_set_params():
    """[Model Selection] Test run with preprocessing, sep param dists."""
    evl = Evaluator(rmse, cv=10, shuffle=False, n_jobs=1, random_state=100)

    params = {('no', 'ols'): {'offset': randint(3, 6)},
              ('pr', 'ols'): {'offset': randint(11, 15)},
              }

    # Fitting
    evl.fit(X, y,
            estimators={'pr': [OLS()], 'no': [OLS()]},
            param_dicts=params,
            preprocessing={'pr': [Scale()], 'no': []},
            n_iter=3)

    np.testing.assert_approx_equal(
            evl.summary['test_score_mean'][('no', 'ols')], 605.04603123784148)
    np.testing.assert_approx_equal(
            evl.summary['test_score_mean'][('pr', 'ols')], 1268.5505117686976)

    assert evl.summary['params'][('no', 'ols')]['offset'] == 3
    assert evl.summary['params'][('pr', 'ols')]['offset'] == 11
