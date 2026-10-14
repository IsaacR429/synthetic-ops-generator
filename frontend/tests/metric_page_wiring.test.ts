import test from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const eventInspectionPage = readFileSync(
    "src/pages/EventInspectionPage.tsx",
    "utf8",
)

test("event inspection keeps metric and capacity classifications distinct", () => {
    assert.match(
        eventInspectionPage,
        /getMetricClassification\(/,
    )

    assert.match(
        eventInspectionPage,
        /getCapacityClassification\(/,
    )

    assert.match(
        eventInspectionPage,
        /Metric Classification/,
    )

    assert.match(
        eventInspectionPage,
        /Capacity Classification/,
    )
})
