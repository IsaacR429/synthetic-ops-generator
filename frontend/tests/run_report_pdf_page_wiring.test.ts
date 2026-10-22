import test from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"

const runDetailPage = readFileSync(
    "src/pages/RunDetailPage.tsx",
    "utf8",
)


test("run detail exposes the PDF report download", () => {
    assert.match(
        runDetailPage,
        /buildRunReportPdfUrl/,
    )

    assert.match(
        runDetailPage,
        /buildRunReportPdfUrl\(\s*run\.run_id\s*\)/,
    )

    assert.match(
        runDetailPage,
        />\s*Download PDF\s*</,
    )

    assert.match(
        runDetailPage,
        /href={buildRunReportPdfUrl\(run\.run_id\)}/,
    )

    assert.match(
        runDetailPage,
        /download/,
    )
})
