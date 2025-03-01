import numpy as np
from sklearn.model_selection import train_test_split
import pytest
import matplotlib.pyplot as plt

from scipy.special import factorial

from cyclic_boosting import flags, common_smoothers, observers
from cyclic_boosting.smoothing.onedim import SeasonalSmoother, IsotonicRegressor
from cyclic_boosting.pipelines import (
    pipeline_CBPoissonRegressor,
    pipeline_CBClassifier,
    pipeline_CBLocationRegressor,
    pipeline_CBExponential,
    pipeline_CBNBinomRegressor,
    pipeline_CBNBinomC,
    pipeline_CBGBSRegressor,
    pipeline_CBMultiplicativeQuantileRegressor,
    pipeline_CBAdditiveQuantileRegressor,
    pipeline_CBMultiplicativeGenericCRegressor,
    pipeline_CBAdditiveGenericCRegressor,
    pipeline_CBGenericClassifier,
)
from cyclic_boosting.quantile_matching import (
    quantile_fit_gamma,
    quantile_fit_nbinom,
    quantile_fit_spline,
    J_QPD_S,
    QPD_RegressorChain,
)
from cyclic_boosting.utils import smear_discrete_cdftruth
from cyclic_boosting.interaction_selection import select_interaction_terms_anova
from tests.utils import plot_CB, costs_mad, costs_mse

np.random.seed(42)


@pytest.fixture(scope="function")
def cb_poisson_regressor_model(features, feature_properties):
    explicit_smoothers = {
        ("dayofyear",): SeasonalSmoother(order=3),
        ("price_ratio",): IsotonicRegressor(increasing=False),
    }

    plobs = [
        observers.PlottingObserver(iteration=1),
        observers.PlottingObserver(iteration=-1),
    ]

    CB_pipeline = pipeline_CBPoissonRegressor(
        feature_properties=feature_properties,
        feature_groups=features,
        observers=plobs,
        maximal_iterations=50,
        smoother_choice=common_smoothers.SmootherChoiceGroupBy(
            use_regression_type=True, use_normalization=False, explicit_smoothers=explicit_smoothers
        ),
    )

    return CB_pipeline


def test_poisson_regression(is_plot, prepare_data, cb_poisson_regressor_model):
    X, y = prepare_data

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.33, random_state=42)

    CB_est = cb_poisson_regressor_model
    CB_est.fit(X_train, y_train)

    if is_plot:
        plot_CB("analysis_CB_iterfirst", [CB_est[-1].observers[0]], CB_est[-2])
        plot_CB("analysis_CB_iterlast", [CB_est[-1].observers[-1]], CB_est[-2])

    yhat = CB_est.predict(X_test)

    mad = np.nanmean(np.abs(y_test - yhat))
    np.testing.assert_almost_equal(mad, 1.688, 3)


def test_poisson_regression_interactions_selection(prepare_data, feature_properties, features, is_plot):
    X, y = prepare_data

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.33, random_state=42)

    best_interaction_term_features = select_interaction_terms_anova(X_train, y_train, feature_properties, 3, 5)

    expected = [
        ("PG_ID_3", "L_ID"),
        ("PG_ID_3", "PROMOTION_TYPE"),
        ("L_ID", "PROMOTION_TYPE"),
        ("PG_ID_3", "L_ID", "dayofweek"),
        ("PG_ID_3", "L_ID", "PROMOTION_TYPE"),
    ]
    assert best_interaction_term_features == expected

    features_ext = features.copy()
    features_ext += best_interaction_term_features

    explicit_smoothers = {
        ("dayofyear",): SeasonalSmoother(order=3),
        ("price_ratio",): IsotonicRegressor(increasing=False),
    }

    plobs = [
        observers.PlottingObserver(iteration=1),
        observers.PlottingObserver(iteration=-1),
    ]

    CB_est = pipeline_CBPoissonRegressor(
        feature_properties=feature_properties,
        feature_groups=features_ext,
        observers=plobs,
        maximal_iterations=50,
        smoother_choice=common_smoothers.SmootherChoiceGroupBy(
            use_regression_type=True, use_normalization=False, explicit_smoothers=explicit_smoothers
        ),
    )
    CB_est.fit(X_train, y_train)

    if is_plot:
        plot_CB("analysis_CB_iterfirst", [CB_est[-1].observers[0]], CB_est[-2])
        plot_CB("analysis_CB_iterlast", [CB_est[-1].observers[-1]], CB_est[-2])

    yhat = CB_est.predict(X_test)

    mad = np.nanmean(np.abs(y_test - yhat))
    np.testing.assert_almost_equal(mad, 1.641, 3)


@pytest.fixture(scope="function")
def cb_poisson_regressor_model_ordered_smoothing(features, feature_properties):
    explicit_smoothers = {
        ("dayofyear",): SeasonalSmoother(order=3),
        ("price_ratio",): IsotonicRegressor(increasing=False),
    }

    plobs = [
        observers.PlottingObserver(iteration=1),
        observers.PlottingObserver(iteration=-1),
    ]

    fp = feature_properties.copy()
    fp["P_ID"] = flags.IS_ORDERED
    fp["PG_ID_3"] = flags.IS_ORDERED
    fp["L_ID"] = flags.IS_ORDERED
    fp["dayofweek"] = flags.IS_ORDERED
    fp["price_ratio"] = flags.IS_ORDERED

    CB_pipeline = pipeline_CBPoissonRegressor(
        feature_properties=fp,
        feature_groups=features,
        observers=plobs,
        maximal_iterations=50,
        smoother_choice=common_smoothers.SmootherChoiceGroupBy(
            use_regression_type=True, use_normalization=False, explicit_smoothers=explicit_smoothers
        ),
    )

    return CB_pipeline


def test_poisson_regression_ordered_smoothing(is_plot, prepare_data, cb_poisson_regressor_model_ordered_smoothing):
    X, y = prepare_data

    # make the effect visible with high-uncertainty bin
    X_special = X.copy()
    X_special["P_ID"].iloc[1] = 11.5

    CB_est = cb_poisson_regressor_model_ordered_smoothing
    CB_est.fit(X_special, y)

    if is_plot:
        plot_CB("analysis_CB_iterfirst_ordered", [CB_est[-1].observers[0]], CB_est[-2])
        plot_CB("analysis_CB_iterlast_ordered", [CB_est[-1].observers[-1]], CB_est[-2])

    yhat = CB_est.predict(X_special)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.70, 3)


@pytest.fixture(scope="function")
def cb_poisson_regressor_model_hierarchical(features, feature_properties):
    explicit_smoothers = {
        ("dayofyear",): SeasonalSmoother(order=3),
        ("price_ratio",): IsotonicRegressor(increasing=False),
    }

    plobs = [
        observers.PlottingObserver(iteration=1),
        observers.PlottingObserver(iteration=4),
        observers.PlottingObserver(iteration=-1),
    ]

    CB_pipeline = pipeline_CBPoissonRegressor(
        feature_properties=feature_properties,
        feature_groups=[
            "PG_ID_3",
            "P_ID",
            "L_ID",
            ("P_ID", "L_ID"),
            "dayofweek",
            "PROMOTION_TYPE",
            "dayofyear",
            "price_ratio",
        ],
        hierarchical_feature_groups=[
            "PG_ID_3",
            "P_ID",
            "L_ID",
            ("P_ID", "L_ID"),
            "dayofweek",
            "PROMOTION_TYPE",
            "dayofyear",
            # "price_ratio",
        ],
        observers=plobs,
        maximal_iterations=50,
        smoother_choice=common_smoothers.SmootherChoiceGroupBy(
            use_regression_type=True, use_normalization=False, explicit_smoothers=explicit_smoothers
        ),
    )

    return CB_pipeline


def test_poisson_regression_hierarchical(is_plot, prepare_data, cb_poisson_regressor_model_hierarchical):
    X, y = prepare_data

    CB_est = cb_poisson_regressor_model_hierarchical
    CB_est.fit(X, y)

    if is_plot:
        plot_CB("analysis_CB_iterfirst", [CB_est[-1].observers[0]], CB_est[-2])
        plot_CB("analysis_CB_iterfourth", [CB_est[-1].observers[1]], CB_est[-2])
        plot_CB("analysis_CB_iterlast", [CB_est[-1].observers[-1]], CB_est[-2])

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.699, 3)


def test_poisson_regression_default_features(prepare_data, default_features, feature_properties):
    X, y = prepare_data
    X = X[default_features]

    CB_est = pipeline_CBPoissonRegressor(feature_properties=feature_properties)
    CB_est.fit(X, y)

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.7185, 3)


@pytest.mark.parametrize(("feature_groups", "expected"), [(None, 1.689), ([0, 1, 4, 5], 1.950)])
def test_poisson_regression_ndarray(prepare_data, default_features, feature_properties, feature_groups, expected):
    X, y = prepare_data
    X = X[default_features].to_numpy()

    CB_est = pipeline_CBPoissonRegressor(feature_groups=feature_groups, feature_properties=feature_properties)
    CB_est.fit(X, y)

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, expected, 3)


@pytest.mark.parametrize("regressor", ["BinomRegressor", "PoissonRegressor"])
def test_regression_ndarray_w_feature_properties(prepare_data, default_features, regressor):
    X, y = prepare_data
    X = X[default_features].to_numpy()

    fp = {
        0: flags.IS_UNORDERED,
        2: flags.IS_UNORDERED,
        3: flags.IS_ORDERED,
        5: flags.IS_CONTINUOUS | flags.HAS_MISSING | flags.MISSING_NOT_LEARNED,
        6: flags.IS_ORDERED,
    }

    if regressor == "BinomRegressor":
        CB_est = pipeline_CBNBinomRegressor(feature_properties=fp)
    else:
        CB_est = pipeline_CBPoissonRegressor(feature_properties=fp)

    CB_est.fit(X, y)
    yhat = CB_est.predict(X)
    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.697, 3)


def test_poisson_regression_default_features_and_properties(is_plot, prepare_data, default_features):
    X, y = prepare_data
    X = X[default_features]

    plobs = [
        observers.PlottingObserver(iteration=1),
        observers.PlottingObserver(iteration=-1),
    ]
    CB_est = pipeline_CBPoissonRegressor(
        observers=plobs,
    )
    CB_est.fit(X, y)

    if is_plot:
        plot_CB("analysis_CB_iterfirst", [CB_est[-1].observers[0]], CB_est[-2])
        plot_CB("analysis_CB_iterlast", [CB_est[-1].observers[-1]], CB_est[-2])

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.6982, 3)


def test_poisson_regression_default_features_notaggregated(prepare_data, default_features, feature_properties):
    X, y = prepare_data
    X = X[default_features]

    CB_est = pipeline_CBPoissonRegressor(feature_properties=feature_properties, aggregate=False)
    CB_est.fit(X, y)

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.7144, 3)


def test_nbinom_regression_default_features(prepare_data, default_features, feature_properties):
    X, y = prepare_data
    X = X[default_features]

    CB_est = pipeline_CBNBinomRegressor(
        feature_properties=feature_properties,
        a=1.2,
        c=0.1,
    )
    CB_est.fit(X, y)

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.7198, 3)


@pytest.mark.parametrize(("feature_groups", "expected"), [(None, 1.689), ([0, 1, 4, 5], 1.950)])
def test_nbinom_regression_ndarray(prepare_data, default_features, feature_properties, feature_groups, expected):
    X, y = prepare_data
    X = X[default_features].to_numpy()

    fp = feature_properties
    CB_est = pipeline_CBNBinomRegressor(
        feature_groups=feature_groups,
        feature_properties=fp,
    )
    CB_est.fit(X, y)

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, expected, 3)


@pytest.fixture(scope="function")
def cb_exponential_regressor_model(features, feature_properties):
    features_noprice = features.copy()
    features_noprice.remove("price_ratio")
    price_features = [
        "L_ID",
        "PG_ID_1",
        "PG_ID_2",
        "PG_ID_3",
        "P_ID",
        "dayofweek",
    ]

    feature_properties = feature_properties
    explicit_smoothers = {
        ("dayofyear",): SeasonalSmoother(order=3),
        ("price_ratio",): IsotonicRegressor(increasing=False),
    }

    plobs = [
        observers.PlottingObserver(iteration=1),
        observers.PlottingObserver(iteration=-1),
    ]

    CB_pipeline = pipeline_CBExponential(
        feature_properties=feature_properties,
        standard_feature_groups=features_noprice,
        external_feature_groups=price_features,
        external_colname="price_ratio",
        observers=plobs,
        maximal_iterations=50,
        smoother_choice=common_smoothers.SmootherChoiceGroupBy(
            use_regression_type=True, use_normalization=False, explicit_smoothers=explicit_smoothers
        ),
    )

    return CB_pipeline


def test_exponential_regression(is_plot, prepare_data, cb_exponential_regressor_model):
    X, y = prepare_data
    X.loc[X["price_ratio"] == np.nan, "price_ratio"] = 1.0

    CB_est = cb_exponential_regressor_model
    CB_est.fit(X, y)

    if is_plot:
        plot_CB("analysis_CB_iterfirst", [CB_est[-1].observers[0]], CB_est[-2])
        plot_CB("analysis_CB_iterlast", [CB_est[-1].observers[-1]], CB_est[-2])

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.7203, 3)


@pytest.fixture(scope="function")
def cb_classifier_model(features, feature_properties):
    explicit_smoothers = {
        ("dayofyear",): SeasonalSmoother(order=3),
        ("price_ratio",): IsotonicRegressor(increasing=False),
    }

    plobs = [observers.PlottingObserver(iteration=-1)]

    CB_pipeline = pipeline_CBClassifier(
        feature_properties=feature_properties,
        feature_groups=features,
        observers=plobs,
        maximal_iterations=50,
        smoother_choice=common_smoothers.SmootherChoiceGroupBy(
            use_regression_type=True, use_normalization=False, explicit_smoothers=explicit_smoothers
        ),
    )

    return CB_pipeline


def test_classification(is_plot, prepare_data, cb_classifier_model):
    X, y = prepare_data
    y = y >= 3

    CB_est = cb_classifier_model
    CB_est.fit(X, y)

    if is_plot:
        plot_CB("analysis_CB_iterlast", [CB_est[-1].observers[-1]], CB_est[-2])

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 0.3075, 3)


def test_location_regression_default_features(is_plot, feature_properties, default_features, prepare_data):
    X, y = prepare_data
    X = X[default_features]

    fp = feature_properties

    CB_est = pipeline_CBLocationRegressor(feature_properties=fp)
    CB_est.fit(X, y)

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.7511, 3)


@pytest.fixture(scope="function")
def cb_width_model(feature_properties):
    features = ["dayofweek", "L_ID", "PG_ID_3", "PROMOTION_TYPE"]

    explicit_smoothers = {}

    plobs = [observers.PlottingObserver(iteration=-1)]

    CB_pipeline = pipeline_CBNBinomC(
        mean_prediction_column="yhat_mean",
        feature_properties=feature_properties,
        feature_groups=features,
        observers=plobs,
        maximal_iterations=50,
        smoother_choice=common_smoothers.SmootherChoiceGroupBy(
            use_regression_type=True, use_normalization=False, explicit_smoothers=explicit_smoothers
        ),
    )

    return CB_pipeline


def test_width_regression_default_features(feature_properties, default_features, prepare_data, cb_width_model):
    X, y = prepare_data
    X = X[default_features]

    fp = feature_properties
    CB_est = pipeline_CBPoissonRegressor(feature_properties=fp)
    CB_est.fit(X, y)
    yhat = CB_est.predict(X)
    X = X.assign(yhat_mean=yhat)

    CB_est_width = cb_width_model
    CB_est_width.fit(X, y)
    c = CB_est_width.predict(X)
    np.testing.assert_almost_equal(c.mean(), 0.365, 3)


def test_GBS_regression_default_features(is_plot, feature_properties, default_features, prepare_data):
    X, y = prepare_data
    X = X[default_features]

    y_GBS = y.copy()
    y_GBS[1000:10000] = -y_GBS[1000:10000]

    CB_est = pipeline_CBGBSRegressor(feature_properties=feature_properties)
    CB_est.fit(X, y_GBS)

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y_GBS - yhat))
    np.testing.assert_almost_equal(mad, 2.5755, 3)


def evaluate_quantile(y, yhat):
    quantile_acc = (y <= yhat).mean()
    return quantile_acc


def cb_multiplicative_quantile_regressor_model(quantile, features, feature_properties):
    explicit_smoothers = {
        ("dayofyear",): SeasonalSmoother(order=3),
        ("price_ratio",): IsotonicRegressor(increasing=False),
    }

    plobs = [
        observers.PlottingObserver(iteration=1),
        observers.PlottingObserver(iteration=-1),
    ]

    CB_pipeline = pipeline_CBMultiplicativeQuantileRegressor(
        quantile=quantile,
        feature_properties=feature_properties,
        feature_groups=features,
        observers=plobs,
        maximal_iterations=50,
        smoother_choice=common_smoothers.SmootherChoiceGroupBy(
            use_regression_type=True, use_normalization=False, explicit_smoothers=explicit_smoothers
        ),
    )

    return CB_pipeline


def test_multiplicative_quantile_regression_median(is_plot, prepare_data, features, feature_properties):
    X, y = prepare_data

    quantile = 0.5
    CB_est = cb_multiplicative_quantile_regressor_model(
        quantile=quantile, features=features, feature_properties=feature_properties
    )
    CB_est.fit(X, y)

    if is_plot:
        plot_CB("analysis_CB_iterfirst", [CB_est[-1].observers[0]], CB_est[-2])
        plot_CB("analysis_CB_iterlast", [CB_est[-1].observers[-1]], CB_est[-2])

    yhat = CB_est.predict(X)

    quantile_acc = evaluate_quantile(y, yhat)
    np.testing.assert_almost_equal(quantile_acc, 0.5043, 3)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.6559, 3)


def test_multiplicative_quantile_regression_90(is_plot, prepare_data, features, feature_properties):
    X, y = prepare_data

    quantile = 0.9
    CB_est = cb_multiplicative_quantile_regressor_model(
        quantile=quantile, features=features, feature_properties=feature_properties
    )
    CB_est.fit(X, y)

    if is_plot:
        plot_CB("analysis_CB_iterfirst", [CB_est[-1].observers[0]], CB_est[-2])
        plot_CB("analysis_CB_iterlast", [CB_est[-1].observers[-1]], CB_est[-2])

    yhat = CB_est.predict(X)

    quantile_acc = evaluate_quantile(y, yhat)
    np.testing.assert_almost_equal(quantile_acc, 0.9015, 3)


def test_multiplicative_quantile_regression_pdf_J_QPD_S(is_plot, prepare_data, features, feature_properties):
    X, y = prepare_data

    # empty bin check
    X["P_ID"].iloc[1] = 20

    quantiles = []
    quantile_values = []
    for quantile in [0.2, 0.5, 0.8]:
        CB_est = cb_multiplicative_quantile_regressor_model(
            quantile=quantile, features=features, feature_properties=feature_properties
        )
        CB_est.fit(X, y)
        yhat = CB_est.predict(X)
        quantile_values.append(yhat)
        quantiles.append(quantile)

    quantiles = np.asarray(quantiles)
    quantile_values = np.asarray(quantile_values)

    cdf_truth_list = []
    n_samples = len(X)
    for i in range(n_samples):
        try:
            j_qpd_s = J_QPD_S(0.2, quantile_values[0, i], quantile_values[1, i], quantile_values[2, i])
        except ValueError:
            continue
        np.testing.assert_almost_equal(j_qpd_s.ppf(0.2), quantile_values[0, i], 3)
        np.testing.assert_almost_equal(j_qpd_s.ppf(0.5), quantile_values[1, i], 3)
        np.testing.assert_almost_equal(j_qpd_s.ppf(0.8), quantile_values[2, i], 3)

        if is_plot:
            cdf_truth = smear_discrete_cdftruth(j_qpd_s.cdf, y[i])
            cdf_truth_list.append(cdf_truth)

            if i == 24:
                plt.plot([0.2, 0.5, 0.8], [quantile_values[0, i], quantile_values[1, i], quantile_values[2, i]], "ro")
                xs = np.linspace(0.0, 1.0, 100)
                plt.plot(xs, j_qpd_s.ppf(xs))
                plt.savefig("J_QPD_S_integration_" + str(i) + ".png")
                plt.clf()

    if is_plot:
        cdf_truth = np.asarray(cdf_truth_list)
        plt.hist(cdf_truth[cdf_truth > 0], bins=30)
        plt.savefig("J_QPD_S_cdf_truth_histo.png")
        plt.clf()


def test_qpd_regression(is_plot, prepare_data, features, feature_properties):
    X, y = prepare_data

    est = QPD_RegressorChain(
        pipeline_CBAdditiveQuantileRegressor(
            feature_groups=features, feature_properties=feature_properties, quantile=0.5
        ),
        pipeline_CBAdditiveQuantileRegressor(
            feature_groups=features, feature_properties=feature_properties, quantile=0.5
        ),
        pipeline_CBAdditiveQuantileRegressor(
            feature_groups=features, feature_properties=feature_properties, quantile=0.5
        ),
        "S",
    )
    est.fit(X, y)

    np.testing.assert_almost_equal(est.shape, 12.151, 3)

    pred_lowq, pred_median, pred_highq, qpd = est.predict(X)

    np.testing.assert_almost_equal(np.mean(pred_lowq), 1.17, 3)
    np.testing.assert_almost_equal(np.mean(pred_median), 2.324, 3)
    np.testing.assert_almost_equal(np.mean(pred_highq), 3.867, 3)

    cdf_truth_list = []
    for i in range(len(X)):
        np.testing.assert_almost_equal(qpd[i].ppf(est.alpha), pred_lowq[i], 3)
        np.testing.assert_almost_equal(qpd[i].ppf(0.5), pred_median[i], 3)
        np.testing.assert_almost_equal(qpd[i].ppf(1 - est.alpha), pred_highq[i], 3)

        if is_plot:
            cdf_truth = smear_discrete_cdftruth(qpd[i].cdf, y[i])
            cdf_truth_list.append(cdf_truth)

            if i == 24:
                plt.plot([est.alpha, 0.5, 1 - est.alpha], [pred_lowq[i], pred_median[i], pred_highq[i]], "ro")
                xs = np.linspace(0.0, 1.0, 100)
                plt.plot(xs, qpd[i].ppf(xs))
                plt.savefig("QPD_regression_integration_" + str(i) + ".png")
                plt.clf()

    if is_plot:
        cdf_truth = np.asarray(cdf_truth_list)
        plt.hist(cdf_truth[cdf_truth > 0], bins=30)
        plt.savefig("QPD_regression_cdf_truth_histo.png")
        plt.clf()


@pytest.mark.skip(reason="Long running time")
def test_multiplicative_quantile_regression_spline(is_plot, prepare_data, features, feature_properties):
    X, y = prepare_data

    quantiles = []
    quantile_values = []
    for quantile in [0.1, 0.3, 0.5, 0.7, 0.9]:
        CB_est = cb_multiplicative_quantile_regressor_model(
            quantile=quantile, features=features, feature_properties=feature_properties
        )
        CB_est.fit(X, y)
        yhat = CB_est.predict(X)
        quantile_values.append(yhat)
        quantiles.append(quantile)

    quantiles = np.asarray(quantiles)
    quantile_values = np.asarray(quantile_values)

    i = 24
    spl_fit = quantile_fit_spline(quantiles, quantile_values[:, i])
    np.testing.assert_almost_equal(spl_fit(0.2), 0.529, 3)
    np.testing.assert_almost_equal(spl_fit(0.5), 2.193, 3)
    np.testing.assert_almost_equal(spl_fit(0.8), 4.21, 3)

    if is_plot:
        plt.plot(quantiles, quantile_values[:, i], "ro")
        xs = np.linspace(0.0, 1.0, 100)
        plt.plot(xs, spl_fit(xs))
        plt.savefig("spline_integration" + str(i) + ".png")
        plt.clf()


@pytest.mark.skip(reason="Long running time")
def test_multiplicative_quantile_regression_pdf_gamma(is_plot, prepare_data, features, feature_properties):
    X, y = prepare_data

    quantiles = []
    quantile_values = []
    for quantile in [0.1, 0.3, 0.5, 0.7, 0.9]:
        CB_est = cb_multiplicative_quantile_regressor_model(
            quantile=quantile, features=features, feature_properties=feature_properties
        )
        CB_est.fit(X, y)
        yhat = CB_est.predict(X)
        quantile_values.append(yhat)
        quantiles.append(quantile)

    quantiles = np.asarray(quantiles)
    quantile_values = np.asarray(quantile_values)

    cdf_truth_list = []
    n_samples = len(X)
    for i in range(n_samples):
        if i == 24:
            gamma_fit = quantile_fit_gamma(quantiles, quantile_values[:, i])
            np.testing.assert_almost_equal(gamma_fit(0.2), 0.779, 3)
            np.testing.assert_almost_equal(gamma_fit(0.5), 1.986, 3)
            np.testing.assert_almost_equal(gamma_fit(0.8), 4.097, 3)

            if is_plot:
                plt.plot(quantiles, quantile_values[:, i], "ro")
                xs = np.linspace(0.0, 1.0, 100)
                plt.plot(xs, gamma_fit(xs))
                plt.savefig("gamma_integration_" + str(i) + ".png")
                plt.clf()

        if is_plot:
            gamma_fit_cdf = quantile_fit_gamma(quantiles, quantile_values[:, i], mode="cdf")
            cdf_truth = smear_discrete_cdftruth(gamma_fit_cdf, y[i])
            cdf_truth_list.append(cdf_truth)

    cdf_truth = np.asarray(cdf_truth_list)
    if is_plot:
        plt.hist(cdf_truth[cdf_truth > 0], bins=30)
        plt.savefig("gamma_cdf_truth_histo.png")
        plt.clf()


@pytest.mark.skip(reason="Long running time")
def test_multiplicative_quantile_regression_pdf_nbinom(is_plot, prepare_data, features, feature_properties):
    X, y = prepare_data

    quantiles = []
    quantile_values = []
    for quantile in [0.1, 0.3, 0.5, 0.7, 0.9]:
        CB_est = cb_multiplicative_quantile_regressor_model(
            quantile=quantile, features=features, feature_properties=feature_properties
        )
        CB_est.fit(X, y)
        yhat = CB_est.predict(X)
        quantile_values.append(yhat)
        quantiles.append(quantile)

    quantiles = np.asarray(quantiles)
    quantile_values = np.asarray(quantile_values)

    cdf_truth_list = []
    n_samples = len(X)
    for i in range(n_samples):
        if i == 24:
            nbinom_fit = quantile_fit_nbinom(quantiles, quantile_values[:, i])
            np.testing.assert_equal(nbinom_fit(0.2), 1)
            np.testing.assert_equal(nbinom_fit(0.5), 2)
            np.testing.assert_equal(nbinom_fit(0.8), 4)

            if is_plot:
                plt.plot(quantiles, quantile_values[:, i], "ro")
                xs = np.linspace(0.0, 1.0, 100)
                plt.plot(xs, nbinom_fit(xs))
                plt.savefig("nbinom_integration_" + str(i) + ".png")
                plt.clf()

        if is_plot:
            nbinom_fit_cdf = quantile_fit_nbinom(quantiles, quantile_values[:, i], mode="cdf")
            cdf_truth = smear_discrete_cdftruth(nbinom_fit_cdf, y[i])
            cdf_truth_list.append(cdf_truth)

    cdf_truth = np.asarray(cdf_truth_list)
    if is_plot:
        plt.hist(cdf_truth, bins=30)
        plt.savefig("nbinom_cdf_truth_histo.png")
        plt.clf()


def test_additive_quantile_regression_median(is_plot, prepare_data, default_features, feature_properties):
    X, y = prepare_data
    X = X[default_features]

    CB_est = pipeline_CBAdditiveQuantileRegressor(
        feature_properties=feature_properties,
        quantile=0.5,
    )
    CB_est.fit(X, y)

    yhat = CB_est.predict(X)

    quantile_acc = evaluate_quantile(y, yhat)
    np.testing.assert_almost_equal(quantile_acc, 0.4950, 3)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.7062, 3)


def test_additive_quantile_regression_90(is_plot, prepare_data, default_features, feature_properties):
    X, y = prepare_data
    X = X[default_features]

    CB_est = pipeline_CBAdditiveQuantileRegressor(
        feature_properties=feature_properties,
        quantile=0.9,
    )
    CB_est.fit(X, y)

    yhat = CB_est.predict(X)

    quantile_acc = evaluate_quantile(y, yhat)
    np.testing.assert_almost_equal(quantile_acc, 0.8934, 3)


def test_additive_regression_mad(is_plot, prepare_data, default_features, feature_properties):
    X, y = prepare_data
    X = X[default_features]

    plobs = [
        observers.PlottingObserver(iteration=1),
        observers.PlottingObserver(iteration=-1),
    ]

    CB_est = pipeline_CBAdditiveGenericCRegressor(
        feature_properties=feature_properties,
        costs=costs_mad,
        observers=plobs,
    )
    CB_est.fit(X, y)

    if is_plot:
        plot_CB("analysis_CB_iterlast", [CB_est[-1].observers[-1]], CB_est[-2])

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.7062, 3)


def test_additive_regression_mse(is_plot, prepare_data, default_features, feature_properties):
    X, y = prepare_data
    X = X[default_features]

    CB_est = pipeline_CBAdditiveGenericCRegressor(
        feature_properties=feature_properties,
        costs=costs_mse,
    )
    CB_est.fit(X, y)

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.738, 3)


def test_multiplicative_regression_mad(is_plot, prepare_data, default_features, feature_properties):
    X, y = prepare_data

    X = X[default_features]

    CB_est = pipeline_CBMultiplicativeGenericCRegressor(
        feature_properties=feature_properties,
        costs=costs_mad,
    )
    CB_est.fit(X, y)

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.6705, 3)


def test_multiplicative_regression_mse(is_plot, prepare_data, default_features, feature_properties):
    X, y = prepare_data

    X = X[default_features]

    CB_est = pipeline_CBMultiplicativeGenericCRegressor(
        feature_properties=feature_properties,
        costs=costs_mse,
    )
    CB_est.fit(X, y)

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.7171, 3)


def poisson_likelihood(prediction, y, weights):
    negative_log_likelihood = np.nanmean(prediction + np.log(factorial(y)) - np.log(prediction) * y)
    return negative_log_likelihood


@pytest.mark.skip(reason="Long running time")
def test_multiplicative_regression_likelihood(is_plot, prepare_data, default_features, feature_properties):
    X, y = prepare_data
    X = X[default_features]

    CB_est = pipeline_CBMultiplicativeGenericCRegressor(
        feature_properties=feature_properties,
        costs=poisson_likelihood,
    )
    CB_est.fit(X, y)

    if is_plot:
        plot_CB("analysis_CB_iterlast", [CB_est[-1].observers[-1]], CB_est[-2])

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 1.9310, 3)


def costs_logloss(prediction, y, weights):
    prediction = np.where(prediction < 0.001, 0.001, prediction)
    prediction = np.where(prediction > 0.999, 0.999, prediction)
    return -np.nanmean(y * np.log(prediction) + (1 - y) * np.log(1 - prediction))


@pytest.fixture(scope="function")
def cb_classifier_logloss_model(features, feature_properties):
    explicit_smoothers = {
        ("dayofyear",): SeasonalSmoother(order=3),
        ("price_ratio",): IsotonicRegressor(increasing=False),
    }

    plobs = [observers.PlottingObserver(iteration=-1)]

    CB_pipeline = pipeline_CBGenericClassifier(
        feature_properties=feature_properties,
        feature_groups=features,
        observers=plobs,
        maximal_iterations=50,
        smoother_choice=common_smoothers.SmootherChoiceGroupBy(
            use_regression_type=True, use_normalization=False, explicit_smoothers=explicit_smoothers
        ),
        costs=costs_logloss,
    )

    return CB_pipeline


def test_classification_logloss(is_plot, prepare_data, cb_classifier_logloss_model):
    X, y = prepare_data
    y = y >= 3

    CB_est = cb_classifier_logloss_model
    CB_est.fit(X, y)

    if is_plot:
        plot_CB("analysis_CB_iterlast", [CB_est[-1].observers[-1]], CB_est[-2])

    yhat = CB_est.predict(X)

    mad = np.nanmean(np.abs(y - yhat))
    np.testing.assert_almost_equal(mad, 0.404, 3)
