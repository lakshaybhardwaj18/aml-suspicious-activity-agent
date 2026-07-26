const pptxgen = require("pptxgenjs");

const NAVY = "1E2761";
const ICE = "CADCFC";
const WHITE = "FFFFFF";
const RISK_RED = "C0392B";
const RISK_AMBER = "F39C12";
const RISK_GREEN = "27AE60";
const SLATE = "44506B";

let pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5

// ============================= SLIDE 1 =============================
// Solution overview + architecture
let s1 = pres.addSlide();
s1.background = { color: WHITE };

s1.addText("AI-Powered Suspicious Activity Detection", {
  x: 0.5, y: 0.35, w: 12.3, h: 0.6,
  fontFace: "Cambria", fontSize: 30, bold: true, color: NAVY, margin: 0,
});
s1.addText("A query-aware AML agent that dynamically plans tool calls, flags suspicious transactions, and explains why", {
  x: 0.5, y: 0.92, w: 12.3, h: 0.4,
  fontFace: "Calibri", fontSize: 15, italic: true, color: SLATE, margin: 0,
});

// Architecture flow: 6 components as connected cards
const cards = [
  { title: "Agent\nOrchestrator", desc: "Parses intent, filters\n& target pattern; builds\na dynamic plan", color: NAVY },
  { title: "EDA Tool", desc: "Profiles data &\nbaseline behavior\n(exploratory queries)", color: SLATE },
  { title: "Feature\nEngineering", desc: "Frequency, rolling sums,\nvelocity, deviation —\ncomputed on demand", color: SLATE },
  { title: "Anomaly\nDetection", desc: "Rule-based +\nIsolation Forest scoring\nfor AML patterns", color: SLATE },
  { title: "Risk\nClassification", desc: "Scores → \nlow / medium / high", color: SLATE },
  { title: "Explanation\nComponent", desc: "Natural-language reason\n+ escalation:\nmonitor / review / report", color: NAVY },
];

const cardW = 1.95, cardGap = 0.15, startX = 0.5, cardY = 1.65, cardH = 1.75;
cards.forEach((c, i) => {
  const x = startX + i * (cardW + cardGap);
  s1.addShape("roundRect", {
    x, y: cardY, w: cardW, h: cardH, rectRadius: 0.08,
    fill: { color: c.color }, line: { type: "none" },
    shadow: { type: "outer", color: "000000", opacity: 0.25, blur: 6, offset: 2, angle: 90 },
  });
  s1.addText(c.title, {
    x: x + 0.08, y: cardY + 0.15, w: cardW - 0.16, h: 0.6,
    fontFace: "Calibri", fontSize: 13.5, bold: true, color: WHITE, align: "center", margin: 0,
  });
  s1.addText(c.desc, {
    x: x + 0.1, y: cardY + 0.75, w: cardW - 0.2, h: cardH - 0.85,
    fontFace: "Calibri", fontSize: 9.5, color: ICE, align: "center", margin: 0,
  });
  if (i < cards.length - 1) {
    s1.addText("\u25B6", {
      x: x + cardW + 0.005, y: cardY + cardH / 2 - 0.18, w: 0.14, h: 0.36,
      fontFace: "Arial", fontSize: 13, color: NAVY, align: "center", margin: 0,
    });
  }
});

s1.addText("Dynamic execution plan (not a fixed pipeline) — tools are invoked only when the query calls for them", {
  x: 0.5, y: 3.6, w: 12.3, h: 0.35,
  fontFace: "Calibri", fontSize: 11.5, italic: true, color: SLATE, align: "center", margin: 0,
});

// Bottom row: solution summary stat callouts
const stats = [
  { n: "50,000", l: "transactions profiled" },
  { n: "5", l: "AML pattern types targeted" },
  { n: "82%", l: "recall on suspicious activity" },
  { n: "3", l: "escalation tiers: monitor / review / report" },
];
const statW = 2.95, statGap = 0.2, statStartX = 0.5, statY = 4.25;
stats.forEach((st, i) => {
  const x = statStartX + i * (statW + statGap);
  s1.addShape("roundRect", {
    x, y: statY, w: statW, h: 1.55, rectRadius: 0.08,
    fill: { color: "F4F6FB" }, line: { type: "none" },
  });
  s1.addText(st.n, {
    x: x + 0.1, y: statY + 0.15, w: statW - 0.2, h: 0.75,
    fontFace: "Calibri", fontSize: 34, bold: true, color: NAVY, align: "center", margin: 0,
  });
  s1.addText(st.l, {
    x: x + 0.15, y: statY + 0.92, w: statW - 0.3, h: 0.55,
    fontFace: "Calibri", fontSize: 11, color: SLATE, align: "center", margin: 0,
  });
});

s1.addText("Team of 2 · ~22-hour build · Campus Hackathon 2026, Problem Statement 1", {
  x: 0.5, y: 7.05, w: 12.3, h: 0.3,
  fontFace: "Calibri", fontSize: 10, color: SLATE, align: "center", margin: 0,
});

// ============================= SLIDE 2 =============================
// Key technical details: detection logic, calibration, performance
let s2 = pres.addSlide();
s2.background = { color: WHITE };

s2.addText("Detection Logic & Key Technical Details", {
  x: 0.5, y: 0.35, w: 12.3, h: 0.6,
  fontFace: "Cambria", fontSize: 30, bold: true, color: NAVY, margin: 0,
});

// Left column: rule logic summary
s2.addText("Rule-Based Detection (hybrid with ML)", {
  x: 0.5, y: 1.15, w: 5.9, h: 0.4,
  fontFace: "Calibri", fontSize: 17, bold: true, color: NAVY, margin: 0,
});

const rules = [
  { k: "Structuring / Smurfing", v: "Amount just under the $10k reporting threshold, or a burst whose rolling 24h sum crosses it" },
  { k: "Layering / Rapid Movement", v: "Amount + deviation above the customer's own baseline, many counterparties in 7d, or rapid cash-out" },
  { k: "Unusual Amount", v: "Transaction amount deviates \u2265 2\u03C3 from the customer's historical average" },
  { k: "ML layer", v: "Isolation Forest over engineered features catches multivariate anomalies rules miss" },
];
let ry = 1.65;
rules.forEach((r) => {
  s2.addShape("ellipse", { x: 0.5, y: ry + 0.07, w: 0.1, h: 0.1, fill: { color: RISK_RED }, line: { type: "none" } });
  s2.addText([
    { text: r.k + "  ", options: { bold: true, color: NAVY, fontSize: 12.5 } },
    { text: r.v, options: { color: SLATE, fontSize: 11.5 } },
  ], {
    x: 0.75, y: ry - 0.08, w: 5.7, h: 0.75,
    fontFace: "Calibri", margin: 0, valign: "top", lineSpacingMultiple: 1.05,
  });
  ry += 0.85;
});

s2.addText("Calibrated empirically against ground-truth pattern_type labels in the synthetic dataset — full methodology in RULE_CALIBRATION.md", {
  x: 0.5, y: ry + 0.05, w: 5.9, h: 0.5,
  fontFace: "Calibri", fontSize: 10, italic: true, color: SLATE, margin: 0,
});

// Right column: performance chart + table
s2.addImage({
  path: "/home/claude/aml_project/outputs/charts/rule_recall_by_pattern.png",
  x: 6.65, y: 1.1, w: 6.2, h: 3.05,
});

// performance summary mini-table
s2.addTable(
  [
    [{ text: "Detector", options: { bold: true, color: WHITE, fill: { color: NAVY } } },
     { text: "Precision", options: { bold: true, color: WHITE, fill: { color: NAVY } } },
     { text: "Recall", options: { bold: true, color: WHITE, fill: { color: NAVY } } },
     { text: "F1", options: { bold: true, color: WHITE, fill: { color: NAVY } } }],
    ["Rule-based", "0.47", "0.82", "0.60"],
    ["Isolation Forest", "0.42", "0.42", "0.42"],
  ],
  {
    x: 6.65, y: 4.3, w: 6.2, h: 0.9,
    fontFace: "Calibri", fontSize: 11.5, color: SLATE,
    border: { type: "solid", color: "DDE3F0", pt: 1 },
    align: "center", valign: "middle",
  }
);

// Bottom strip: risk classification + escalation logic
s2.addShape("roundRect", {
  x: 0.5, y: 5.5, w: 12.3, h: 1.65, rectRadius: 0.08,
  fill: { color: "F4F6FB" }, line: { type: "none" },
});
s2.addText("Risk Classification \u2192 Escalation", {
  x: 0.75, y: 5.62, w: 4, h: 0.35,
  fontFace: "Calibri", fontSize: 13.5, bold: true, color: NAVY, margin: 0,
});

const riskTiers = [
  { label: "LOW", desc: "final_score < 0.25 \u2192 Monitor", color: RISK_GREEN },
  { label: "MEDIUM", desc: "0.25 \u2013 0.5 \u2192 Review", color: RISK_AMBER },
  { label: "HIGH", desc: "\u2265 0.5 \u2192 Report", color: RISK_RED },
];
let tx0 = 0.75, tw = 3.9;
riskTiers.forEach((t, i) => {
  const x = tx0 + i * (tw + 0.1);
  s2.addShape("roundRect", {
    x, y: 6.05, w: 1.1, h: 0.55, rectRadius: 0.06,
    fill: { color: t.color }, line: { type: "none" },
  });
  s2.addText(t.label, {
    x, y: 6.05, w: 1.1, h: 0.55,
    fontFace: "Calibri", fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0,
  });
  s2.addText(t.desc, {
    x: x + 1.2, y: 6.05, w: tw - 1.2, h: 0.55,
    fontFace: "Calibri", fontSize: 11.5, color: SLATE, valign: "middle", margin: 0,
  });
});

s2.addText("final_score = 0.7 \u00d7 rule_score/5 + 0.3 \u00d7 ml_score \u2014 rules stay authoritative, ML adds a secondary signal", {
  x: 0.75, y: 6.7, w: 11.8, h: 0.35,
  fontFace: "Calibri", fontSize: 10, italic: true, color: SLATE, margin: 0,
});

pres.writeFile({ fileName: "/home/claude/aml_project/outputs/AML_Detection_Deck.pptx" })
  .then(() => console.log("Deck written"));
