import test from "node:test"
import assert from "node:assert/strict"

import {
    buildRunReportPdfUrl,
} from "../src/api/client.ts"


test("run report PDF URL encodes the run identifier", () => {
    assert.equal(
        buildRunReportPdfUrl("RUN/0000035"),
        "/api/runs/RUN%2F0000035/report.pdf",
    )
})


test("run report PDF URL supports standard run identifiers", () => {
    assert.equal(
        buildRunReportPdfUrl("RUN0000035"),
        "/api/runs/RUN0000035/report.pdf",
    )
})
