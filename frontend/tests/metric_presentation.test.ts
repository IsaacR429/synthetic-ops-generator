import test from "node:test"
import assert from "node:assert/strict"

import {
    getMetricPayload,
    getMetricClassification,
    getCapacityClassification,
} from "../src/types/metricPresentation.ts"

test("metric presentation keeps metric and capacity classifications distinct", () => {
    const metric = getMetricPayload({
        metric: {
            name: "cpu_utilisation",
            observed_value: 92.5,
            unit: "percent",
            classification: "warning",
            capacity: {
                capacity_profile_id: "payment_api_capacity",
                classification: "saturated",
                direction: "higher_is_worse",
                pressure_threshold: 75,
                saturation_threshold: 90,
            },
        },
    })

    assert.equal(
        getMetricClassification(metric),
        "warning",
    )

    assert.equal(
        getCapacityClassification(metric),
        "saturated",
    )
})

test("capacity classification is absent when metric has no capacity context", () => {
    const metric = getMetricPayload({
        metric: {
            name: "request_latency",
            observed_value: 125,
            classification: "normal",
        },
    })

    assert.equal(
        getMetricClassification(metric),
        "normal",
    )

    assert.equal(
        getCapacityClassification(metric),
        null,
    )
})
