import test from "node:test"
import assert from "node:assert/strict"

import {
    buildRunEventsExportUrl,
} from "../src/api/client.ts"
import type {
    RunEventQuery,
} from "../src/types/api.ts"


test("run event CSV export URL includes semantic filters", () => {
    const query: RunEventQuery = {
        source_domain: "metric",
        source_system: "synthetic observability",
        event_type: "metric.observed",
        service: "claims_service",
        component: "claims api",
    }

    assert.equal(
        buildRunEventsExportUrl(
            "RUN/0000035",
            query,
        ),
        (
            "/api/runs/RUN%2F0000035/export.csv" +
            "?source_domain=metric" +
            "&source_system=synthetic+observability" +
            "&event_type=metric.observed" +
            "&service=claims_service" +
            "&component=claims+api"
        ),
    )
})


test("run event CSV export URL omits pagination", () => {
    const query: RunEventQuery = {
        source_domain: "metric",
        service: "claims_service",
        after_sequence_number: 200,
        limit: 100,
    }

    const url = buildRunEventsExportUrl(
        "RUN0000035",
        query,
    )

    assert.equal(
        url,
        (
            "/api/runs/RUN0000035/export.csv" +
            "?source_domain=metric" +
            "&service=claims_service"
        ),
    )

    assert.doesNotMatch(
        url,
        /after_sequence_number/,
    )

    assert.doesNotMatch(
        url,
        /limit=/,
    )
})


test("run event CSV export URL supports unfiltered runs", () => {
    assert.equal(
        buildRunEventsExportUrl("RUN0000035"),
        "/api/runs/RUN0000035/export.csv",
    )
})
