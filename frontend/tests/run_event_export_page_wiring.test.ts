import test from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const eventInspectionPage = readFileSync(
    "src/pages/EventInspectionPage.tsx",
    "utf8",
)

test("event inspection exposes CSV export for the applied query", () => {
    assert.match(
        eventInspectionPage,
        /buildRunEventsExportUrl/,
    )

    assert.match(
        eventInspectionPage,
        /buildRunEventsExportUrl\(\s*runId,\s*appliedQuery,?\s*\)/,
    )

    assert.match(
        eventInspectionPage,
        />\s*Download CSV\s*</,
    )

    assert.match(
        eventInspectionPage,
        /href={exportUrl}/,
    )

    assert.match(
        eventInspectionPage,
        /download/,
    )
})

test("event inspection CSV export does not use page cursor", () => {
    assert.doesNotMatch(
        eventInspectionPage,
        /buildRunEventsExportUrl\(\s*runId,\s*\{[^}]*pageCursor/s,
    )

    assert.doesNotMatch(
        eventInspectionPage,
        /buildRunEventsExportUrl\(\s*runId,\s*\{[^}]*EVENT_PAGE_SIZE/s,
    )
})
