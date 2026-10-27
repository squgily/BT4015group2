import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";
import JSZip from "jszip";
import sharp from "sharp";

const projectDir = path.resolve(import.meta.dirname, "..", "..");
const csvPath = path.join(projectDir, "data", "ResidentHouseholdsIncomebyPlanningArea.csv");
const outputDir = path.join(projectDir, "output", "resident-household-income");
const outputPath = path.join(outputDir, "Resident_household_income_by_planning_area.xlsx");
const pngPath = path.join(outputDir, "Resident_household_income_by_planning_area.png");
const workbookPreviewPath = path.join(import.meta.dirname, "income_chart_preview.png");

const csvText = await fs.readFile(csvPath, "utf8");
const rows = csvText.trim().split(/\r?\n/).map((line) => line.split(","));
const sourceHeaders = rows[0];
const sourceData = rows.slice(1).map((row) => [row[0], ...row.slice(1).map(Number)]);

const incomeLabels = [
  "No employed person",
  "Below $1,000",
  "$1,000 - $1,999",
  "$2,000 - $2,999",
  "$3,000 - $3,999",
  "$4,000 - $4,999",
  "$5,000 - $5,999",
  "$6,000 - $6,999",
  "$7,000 - $7,999",
  "$8,000 - $8,999",
  "$9,000 - $9,999",
  "$10,000 - $10,999",
  "$11,000 - $11,999",
  "$12,000 - $12,999",
  "$13,000 - $13,999",
  "$14,000 - $14,999",
  "$15,000 - $17,499",
  "$17,500 - $19,999",
  "$20,000 & over",
];

const seriesColors = [
  "#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5",
  "#70AD47", "#264478", "#9E480E", "#636363", "#997300",
  "#255E91", "#43682B", "#2E75B6", "#F4B183", "#BFBFBF",
  "#FFD966", "#9DC3E6", "#70AD47", "#2F5597",
];

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function buildChartSvg(planningAreaRows) {
  const width = 1800;
  const height = 980;
  const margin = { top: 70, right: 300, bottom: 230, left: 105 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const plotBottom = margin.top + plotHeight;
  const step = plotWidth / planningAreaRows.length;
  const barWidth = Math.min(20, step * 0.48);
  const legendX = margin.left + plotWidth + 35;
  const legendY = margin.top + 65;
  const parts = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`,
    `<rect width="100%" height="100%" fill="#FFFFFF"/>`,
    `<text x="${width / 2}" y="38" text-anchor="middle" font-family="Arial" font-size="24" font-weight="600" fill="#3F3F3F">Monthly household income by planning area of residence</text>`,
  ];

  for (let tick = 0; tick <= 10; tick += 1) {
    const share = tick / 10;
    const y = plotBottom - share * plotHeight;
    parts.push(`<line x1="${margin.left}" y1="${y}" x2="${margin.left + plotWidth}" y2="${y}" stroke="#D9D9D9" stroke-width="1"/>`);
    parts.push(`<text x="${margin.left - 14}" y="${y + 5}" text-anchor="end" font-family="Arial" font-size="13" fill="#333333">${tick * 10}%</text>`);
  }

  planningAreaRows.forEach((row, areaIndex) => {
    const counts = row.slice(2);
    const totalBands = counts.reduce((sum, value) => sum + value, 0);
    const x = margin.left + areaIndex * step + (step - barWidth) / 2;
    let stackedShare = 0;
    counts.forEach((count, bandIndex) => {
      const share = count / totalBands;
      const segmentHeight = share * plotHeight;
      const y = plotBottom - (stackedShare + share) * plotHeight;
      parts.push(`<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${segmentHeight.toFixed(2)}" fill="${seriesColors[bandIndex]}"/>`);
      stackedShare += share;
    });
    const labelX = x + barWidth / 2;
    const labelY = plotBottom + 13;
    parts.push(`<text x="${labelX.toFixed(2)}" y="${labelY}" transform="rotate(-90 ${labelX.toFixed(2)} ${labelY})" text-anchor="end" font-family="Arial" font-size="12" fill="#333333">${escapeXml(row[0])}</text>`);
  });

  parts.push(`<line x1="${margin.left}" y1="${plotBottom}" x2="${margin.left + plotWidth}" y2="${plotBottom}" stroke="#666666" stroke-width="1"/>`);
  parts.push(`<text x="${margin.left + plotWidth / 2}" y="${height - 28}" text-anchor="middle" font-family="Arial" font-size="16" font-weight="600" fill="#333333">Planning Area</text>`);
  parts.push(`<text x="28" y="${margin.top + plotHeight / 2}" transform="rotate(-90 28 ${margin.top + plotHeight / 2})" text-anchor="middle" font-family="Arial" font-size="16" font-weight="600" fill="#333333">Share of Households</text>`);

  [...incomeLabels].reverse().forEach((label, reverseIndex) => {
    const bandIndex = incomeLabels.length - 1 - reverseIndex;
    const y = legendY + reverseIndex * 32;
    parts.push(`<rect x="${legendX}" y="${y - 12}" width="14" height="14" fill="${seriesColors[bandIndex]}"/>`);
    parts.push(`<text x="${legendX + 23}" y="${y}" font-family="Arial" font-size="13" fill="#333333">${escapeXml(label)}</text>`);
  });

  parts.push("</svg>");
  return parts.join("");
}

const workbook = Workbook.create();
const outputSheet = workbook.worksheets.add("Income Distribution");
const sourceSheet = workbook.worksheets.add("Source Data");
const fontFamily = "Arial";

outputSheet.showGridLines = false;
sourceSheet.showGridLines = false;
outputSheet.tabColor = "#2F5597";

// Source data stays intact and numeric so the chart remains auditable and editable.
sourceSheet.getRange("A1").values = [["Source: ResidentHouseholdsIncomebyPlanningArea.csv"]];
sourceSheet.getRange("A2").values = [["Household counts by planning area and monthly household income band"]];
sourceSheet.getRange("A3:U3").values = [sourceHeaders];
sourceSheet.getRange(`A4:U${sourceData.length + 3}`).values = sourceData;
sourceSheet.getRange(`A1:U${sourceData.length + 3}`).format.font = { name: fontFamily, size: 10, color: "#333333" };
sourceSheet.getRange("A1").format.font = { name: fontFamily, size: 12, bold: true, color: "#2F5597" };
sourceSheet.getRange("A2").format.font = { name: fontFamily, size: 10, italic: true, color: "#666666" };
sourceSheet.getRange("A3:U3").format = {
  fill: "#2F5597",
  font: { name: fontFamily, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: "#D9E2F3" },
};
sourceSheet.getRange(`B4:U${sourceData.length + 3}`).format.numberFormat = "#,##0";
sourceSheet.getRange(`A4:U${sourceData.length + 3}`).format.borders = {
  bottom: { style: "thin", color: "#E7E6E6" },
};
sourceSheet.getRange("A:A").format.columnWidth = 20;
sourceSheet.getRange("B:U").format.columnWidth = 14;
sourceSheet.getRange("1:3").format.rowHeight = 24;
sourceSheet.freezePanes.freezeRows(3);

// Main reader-facing chart and its formula-driven percentage table.
outputSheet.getRange("A3:W3").format.borders = {
  bottom: { style: "thin", color: "#B4C6E7" },
};

outputSheet.getRange("A40").values = [["Chart data: share of households within each planning area"]];
outputSheet.getRange("A40").format.font = { name: fontFamily, size: 12, bold: true, color: "#2F5597" };
outputSheet.getRange("A41:T41").values = [["Planning Area", ...incomeLabels]];
outputSheet.getRange("A41:T41").format = {
  fill: "#2F5597",
  font: { name: fontFamily, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: "#D9E2F3" },
};

const planningRows = sourceData.slice(1);
outputSheet.getRange(`A42:A${planningRows.length + 41}`).values = planningRows.map((row) => [row[0]]);
const formulaRows = planningRows.map((_, index) => {
  const sourceRow = index + 5;
  return Array.from({ length: 19 }, (_, bandIndex) => {
    const sourceColumn = String.fromCharCode("C".charCodeAt(0) + bandIndex);
    return `='Source Data'!${sourceColumn}${sourceRow}/SUM('Source Data'!$C${sourceRow}:$U${sourceRow})`;
  });
});
outputSheet.getRange(`B42:T${planningRows.length + 41}`).formulas = formulaRows;
outputSheet.getRange(`A42:T${planningRows.length + 41}`).format.font = { name: fontFamily, size: 10, color: "#333333" };
outputSheet.getRange(`B42:T${planningRows.length + 41}`).format.numberFormat = "0.0%";
outputSheet.getRange(`A42:T${planningRows.length + 41}`).format.borders = {
  bottom: { style: "thin", color: "#E7E6E6" },
};
outputSheet.getRange("A:A").format.columnWidth = 19;
outputSheet.getRange("B:T").format.columnWidth = 14;
outputSheet.getRange("A41:T41").format.rowHeight = 42;
outputSheet.getRange(`A42:T${planningRows.length + 41}`).format.rowHeight = 19;

const chartRange = outputSheet.getRange(`A41:T${planningRows.length + 41}`);
const chart = outputSheet.charts.add("bar", chartRange);
chart.barOptions.direction = "column";
chart.barOptions.grouping = "stacked";
chart.barOptions.gapWidth = 100;
chart.barOptions.overlap = 100;
chart.title = "Monthly household income by planning area of residence";
chart.titleTextStyle.fontSize = 16;
chart.titleTextStyle.typeface = fontFamily;
chart.hasLegend = true;
chart.legend = { position: "right", textStyle: { typeface: fontFamily, fontSize: 9 } };
chart.xAxis = {
  axisType: "textAxis",
  textStyle: { typeface: fontFamily, fontSize: 8 },
  title: { text: "Planning Area" },
};
chart.yAxis = {
  numberFormatCode: "0%",
  numberFormatSourceLinked: false,
  majorUnit: 0.1,
  textStyle: { typeface: fontFamily, fontSize: 9 },
  title: { text: "Share of Households" },
};
chart.axes.valueAxis.minimumScale = 0;
chart.axes.valueAxis.maximumScale = 1;
chart.axes.valueAxis.majorUnit = 0.1;
chart.axes.categoryAxis.textOrientation = -90;
chart.setPosition("A4", "W38");
chart.width = 1700;
chart.height = 760;

chart.series.items.forEach((series, index) => {
  series.fill = seriesColors[index];
});

outputSheet.getRange("A75").values = [["Each planning area is normalized to 100% using the sum of its displayed income bands. The national Total row is excluded."]];
outputSheet.getRange("A75").format.font = { name: fontFamily, size: 10, italic: true, color: "#666666" };

workbook.recalculate();

const tableCheck = await workbook.inspect({
  kind: "table",
  range: "Income Distribution!A40:T45",
  include: "values,formulas",
  tableMaxRows: 8,
  tableMaxCols: 20,
  maxChars: 10000,
});
console.log(tableCheck.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const drawingCheck = await workbook.inspect({
  kind: "drawing",
  sheetId: "Income Distribution",
  maxChars: 8000,
});
console.log(drawingCheck.ndjson);

const preview = await workbook.render({
  sheetName: "Income Distribution",
  range: "A1:W42",
  scale: 1,
  format: "png",
});
await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(workbookPreviewPath, new Uint8Array(await preview.arrayBuffer()));

const chartSvg = buildChartSvg(planningRows);
await sharp(Buffer.from(chartSvg)).png().toFile(pngPath);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);

// The current renderer accepts but does not serialize value-axis bounds or category-label rotation.
// Apply those two standard OOXML chart settings after the artifact-tool export.
const zip = await JSZip.loadAsync(await fs.readFile(outputPath));
const chartEntryName = Object.keys(zip.files).find((name) => /xl\/drawings\/charts\/chart\d+\.xml$/.test(name));
if (!chartEntryName) {
  throw new Error("Exported workbook does not contain a chart definition.");
}
let chartXml = await zip.file(chartEntryName).async("string");
chartXml = chartXml.replace(/(<c:valAx>.*?<c:scaling>)(.*?)(<\/c:scaling>)/s, "$1$2<c:min val=\"0\" /><c:max val=\"1\" />$3");
chartXml = chartXml.replace(/<c:catAx>.*?<\/c:catAx>/s, (categoryAxisXml) =>
  categoryAxisXml.replace(
    '<c:txPr><a:bodyPr anchorCtr="1"',
    '<c:txPr><a:bodyPr anchorCtr="1" rot="-5400000"',
  ),
);
zip.file(chartEntryName, chartXml);
await fs.writeFile(outputPath, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));

console.log(JSON.stringify({ outputPath, pngPath, planningAreas: planningRows.length, incomeBands: incomeLabels.length }));
