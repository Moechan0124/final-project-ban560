// Builds the Results package (Word) for the writing team from outputs/ and figures/.
// Run from the project root: NODE_PATH=<folder with the docx npm package> node tools/build_results_package.js
// The .docx output is ignored by git.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType,
  HeadingLevel, WidthType, BorderStyle, ShadingType, PageNumber, LevelFormat, Footer,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const LINE = 276;

// ---------- data ----------
function csv(name) {
  const text = fs.readFileSync(path.join(ROOT, "outputs", `${name}.csv`), "utf8").trim();
  const parse = (l) => {
    const out = []; let cur = "", q = false;
    for (const ch of l) {
      if (ch === '"') q = !q;
      else if (ch === "," && !q) { out.push(cur); cur = ""; } else cur += ch;
    }
    out.push(cur);
    return out;
  };
  const [head, ...rows] = text.split("\n").map(parse);
  return rows.map((r) => Object.fromEntries(head.map((h, i) => [h, r[i]])));
}
const num = (v, d = 2) => Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const usd = (v, d = 0) => `$${num(v, d)}`;
const pct = (v, d = 0) => `${num(Number(v) * 100, d)}%`;
const by = (rows, k, v) => rows.find((r) => r[k] === v);

const models = csv("model_comparison");
const perm = csv("permutation_importance");
const coefs = csv("elastic_net_coefficients");
const tree = csv("tree_feature_importance").filter((r) => r.model === "Random forest");
const seg = csv("segment_errors");
const segModels = csv("segment_models");
const hoods = csv("neighbourhood_demand");
const roomStay = csv("demand_by_stay_type_room_type");
const propStay = csv("demand_by_stay_type_property_grp");
const fit = csv("fair_price_fit");
const gapSummary = csv("pricing_gap_summary");
const gapQ = csv("gap_quintile_demand");
const hoodGap = csv("neighbourhood_pricing_gap");
const cvRF = csv("cv_results_random_forest");
const cvGBT = csv("cv_results_gbt");
const cvEN = csv("cv_results_elastic_net");

// ---------- helpers ----------
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}
const P = (t) => new Paragraph({ children: runs(t), spacing: { line: LINE, after: 120 } });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const B = (t, level = 0) => new Paragraph({ numbering: { reference: "bullets", level }, children: runs(t), spacing: { line: LINE, after: 40 } });
const gap = () => new Paragraph({ spacing: { after: 120 }, children: [] });

function callout(lines, fill = "EEF4FC") {
  const b = { style: BorderStyle.SINGLE, size: 4, color: "9EC5F4" };
  return new Table({
    width: { size: 9360, type: WidthType.DXA }, columnWidths: [9360],
    rows: [new TableRow({ children: [new TableCell({
      width: { size: 9360, type: WidthType.DXA },
      shading: { fill, type: ShadingType.CLEAR, color: "auto" },
      margins: { top: 120, bottom: 120, left: 180, right: 180 },
      borders: { top: b, bottom: b, left: b, right: b },
      children: lines.map((l) => l.startsWith("• ")
        ? new Paragraph({ numbering: { reference: "bullets", level: 0 }, children: runs(l.slice(2)), spacing: { line: LINE, after: 50 } })
        : new Paragraph({ children: runs(l), spacing: { line: LINE, after: 50 } })),
    })] })],
  });
}

const line = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
function table(title, header, rows, widths, opts = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const left = opts.leftCols || [];
  const cell = (text, i, head, last) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA },
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    shading: head ? { fill: "F2F2F2", type: ShadingType.CLEAR, color: "auto" } : undefined,
    borders: { top: line, bottom: line, left: line, right: line },
    children: [new Paragraph({
      alignment: i === 0 || left.includes(i) ? AlignmentType.LEFT : AlignmentType.RIGHT,
      keepNext: !last && !opts.split,
      children: runs(String(text), { size: opts.size || 19, bold: head }),
    })],
  });
  return [
    new Paragraph({ children: [new TextRun({ text: title, bold: true })], spacing: { before: 200, after: 80 }, keepNext: true }),
    new Table({
      width: { size: total, type: WidthType.DXA }, columnWidths: widths,
      rows: [
        new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, i, true, false)) }),
        ...rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, i, false, ri === rows.length - 1)) })),
      ],
    }),
    gap(),
  ];
}
function figure(title, file, widthIn) {
  const buf = fs.readFileSync(path.join(ROOT, "figures", file));
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20), wpx = widthIn * 96;
  return [
    new Paragraph({ children: [new TextRun({ text: title, bold: true })], spacing: { before: 200, after: 40 }, keepNext: true }),
    new Paragraph({ children: runs(`File: *figures/${file}*`, { size: 18, color: "595959" }), spacing: { after: 60 }, keepNext: true }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: wpx, height: (wpx * h) / w },
        altText: { title, description: title, name: file } })] }),
  ];
}

// ---------- derived values ----------
const m = Object.fromEntries(models.map((r) => [r.model, r]));
const rf = m["Random forest"], base = m["Baseline (neighborhood × room median)"], en = m["Elastic Net linear regression"];
const shortName = { "Baseline (neighborhood × room median)": "Baseline", "OLS linear regression": "OLS", "Elastic Net linear regression": "Elastic Net", "Random forest": "Random forest", "Gradient-boosted trees": "Gradient-boosted trees" };
const coef = (label) => { const r = by(coefs, "label", label); if (!r) throw new Error(label); return Number(r.pct_effect_per_unit); };
const signed = (v, d = 0) => `${v >= 0 ? "+" : "−"}${num(Math.abs(v), d)}%`;
const entireVsPrivate = (Math.exp(Number(by(coefs, "label", "room type: Entire home/apt").coef) - Number(by(coefs, "label", "room type: Private room").coef)) - 1) * 100;
const permRow = (g, model) => perm.find((r) => r.group === g && r.model === model).rmse_increase;
const groups = [...new Set(perm.map((r) => r.group))].sort((a, b) => permRow(b, "Random forest") - permRow(a, "Random forest"));
const q75 = (() => { const v = hoodGap.map((r) => Number(r.demand_index)).sort((a, b) => a - b); const p = 0.75 * (v.length - 1), lo = Math.floor(p); return v[lo] + (v[Math.min(lo + 1, v.length - 1)] - v[lo]) * (p - lo); })();
const candidates = hoodGap.filter((r) => Number(r.demand_index) >= q75 && Number(r.median_location_premium) < -0.05 && Number(r.top_host_share) < 0.5)
  .sort((a, b) => a.median_location_premium - b.median_location_premium);
const q = (stay, i) => gapQ.find((r) => r.stay_type === stay && Number(r.gap_quintile) === i);
const gapShare = (stay, g) => pct(gapSummary.find((r) => r.stay_type === stay && r.gap_group === g).share_of_stay_type, 1);
const segRow = (s) => { const r = by(seg, "segment", s); return [s, num(r.test_listings, 0), num(r.rmse_log, 3), num(r.r2_within, 3), pct(r.median_abs_pct_error)]; };

// ---------- content ----------
const title = [
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "Results Package", bold: true, size: 40 })] }),
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "Final Report: Results, Discussion, Conclusion and Recommendations", size: 26, color: "404040" })] }),
  new Paragraph({ spacing: { after: 240 }, children: runs("Predicting Airbnb Listing Prices with PySpark · BAN5600 · November 2026", { size: 20, color: "595959" }) }),
  callout([
    "**How to use this package**",
    "• Every number here is generated from the *outputs* tables by the project notebooks.",
    "• The bullets are notes for the writers, not final text. The report should use third person, 1.5 line spacing and page numbers at the bottom.",
    "• Tables and figures can be copied into the report; renumber them freely.",
    "• Section 8 lists numbers that changed since the Introduction. Please use the numbers in this package.",
  ]),
];

const r1 = [
  H1("1. Model Performance (RQ2)"),
  ...table("Table 1. Test-set results (3,742 listings, not used in training or tuning)",
    ["Model", "RMSE (log)", "MAE (log)", "R² (log)", "Train R²", "RMSE ($)", "MAE ($)", "Median % error"],
    models.map((r) => [shortName[r.model], num(r.rmse_log, 3), num(r.mae_log, 3), num(r.r2_log, 3), num(r.train_r2_log, 3), usd(r.rmse_usd), usd(r.mae_usd), pct(r.median_abs_pct_error)]),
    [2300, 1000, 1000, 900, 900, 1000, 900, 1360]),
  ...figure("Figure 1. Test-set performance", "figM1_model_comparison.png", 6.5),
  B(`**Answer to RQ2:** yes. The random forest explains ${pct(rf.r2_log, 1)} of the variation in log price, compared with ${pct(base.r2_log, 1)} for the baseline. Half of its dollar predictions are within ${pct(rf.median_abs_pct_error)} of the listed price.`),
  B(`Average dollar error falls from ${usd(base.mae_usd)} (baseline) to ${usd(en.mae_usd)} (Elastic Net) to ${usd(rf.mae_usd)} (random forest).`),
  B(`Tree models beat linear models, which points to non-linear effects and interactions between features.`),
  B(`OLS and Elastic Net are effectively tied, so regularization added little with about 15,000 training listings.`),
  B(`The random forest overfits somewhat (train R² ${num(rf.train_r2_log, 2)}, test R² ${num(rf.r2_log, 2)}), but its test score is still the best.`),
  B(`Dollar RMSE (${usd(rf.rmse_usd)}) is much larger than MAE because a few expensive listings produce large errors. R² in dollars is ${num(rf.r2_usd, 2)}.`),
  ...figure("Figure 2. Predicted vs. actual price, random forest (test set)", "figM2_predicted_vs_actual.png", 3.9),
  B("Predictions follow the diagonal across the price range. The model pulls the extremes toward the middle: the most expensive listings tend to be under-predicted."),
];

const r2 = [
  H1("2. What Drives Price (RQ1)"),
  ...table("Table 2. Permutation importance: rise in test RMSE (log) when a feature family is shuffled",
    ["Feature family", "Random forest", "Elastic Net"],
    groups.map((g) => [g, num(permRow(g, "Random forest"), 3), num(permRow(g, "Elastic Net linear regression"), 3)]),
    [5000, 2180, 2180]),
  ...figure("Figure 3. Permutation importance by feature family", "figM3_permutation_importance.png", 6.0),
  B("**Answer to RQ1:** booking rules, size and capacity, and location matter most, and both model types agree on these three."),
  B("Booking rules rank first, which supports the argument that stay type matters after Local Law 18."),
  B("Reviews, host attributes and license status add comparatively little once the other features are known."),
  ...table("Table 3. Selected Elastic Net effects, holding other features constant",
    ["Feature", "Change in price", "Compared with / unit"], [
      ["30+ night minimum stay", signed(coef("stay type: 30+ nights")), "Under-30-night listings"],
      ["Entire home/apt", signed(coef("room type: Entire home/apt")), "Shared room"],
      ["Private room", signed(coef("room type: Private room"), 1), "Shared room"],
      ["License not reported", signed(coef("license status: Not reported")), "Registered listings"],
      ["License exempt", signed(coef("license status: Exempt")), "Registered listings"],
      ["Shared bath", signed(coef("shared bath")), "Private bath"],
      ["Each extra bedroom", signed(coef("bedrooms")), "Per bedroom"],
      ["Each extra guest", signed(coef("accommodates"), 1), "Per guest"],
      ["Each km from Times Square", signed(coef("km to midtown"), 1), "Per km"],
      ["Gym", signed(coef("amenity: gym")), "Listings without it"],
      ["Building staff", signed(coef("amenity: building staff")), "Listings without it"],
      ["Dishwasher", signed(coef("amenity: dishwasher")), "Listings without it"],
      ["Elevator", signed(coef("amenity: elevator")), "Listings without it"],
      ["Overall rating", signed(coef("review scores rating")), "Per rating point (1–5)"],
      ["Superhost", signed(coef("is superhost"), 1), "Non-superhosts"],
    ], [4000, 1800, 3560], { leftCols: [2] }),
  B(`Reference groups matter. Entire homes are ${signed(coef("room type: Entire home/apt"))} against shared rooms and about ${signed(entireVsPrivate)} against private rooms. Room type and property type are both in the model, so these are partial effects.`),
  B("These are associations, not causal effects. For example, gym and building staff also mark newer, higher-end buildings."),
  B("Reviews in the last 12 months have a negative coefficient: more reviewed listings tend to charge less. Gibbs et al. (2018) report a similar pattern."),
  B("Superhost status has almost no price effect, and a one-point rating difference is large because most ratings sit between 4.7 and 5."),
  ...figure("Figure 4. Largest Elastic Net effects (standardized)", "figM4_elastic_net_effects.png", 6.0),
  ...figure("Figure 5. Top individual features in the random forest", "figM5_tree_importance.png", 6.0),
  B(`Shared bath has the highest impurity importance (${num(tree[0].importance, 3)}). It acts as a proxy for room quality and room type, so the feature-family result in Table 2 is the safer summary.`),
];

const topH = hoods.slice(0, 10);
const r3 = [
  H1("3. Where and What Demand Is Highest (RQ3)"),
  H2("3.1 Neighborhoods"),
  ...table("Table 4. Top 10 neighborhoods by demand index (priced listings; 72 neighborhoods with at least 50)",
    ["Neighborhood", "Borough", "Listings", "Mean open nights", "Mean reviews (12 mo)", "Median price", "Top-host share", "Index"],
    topH.map((r) => [r.neighbourhood, r.borough, num(r.listings, 0), num(r.mean_availability_365, 0), num(r.mean_reviews_ltm, 1), usd(r.median_price), pct(r.top_host_share), num(r.demand_index, 2)]),
    [1900, 1150, 850, 1050, 1150, 1050, 1100, 1110], { leftCols: [1] }),
  ...figure("Figure 6. Neighborhood demand", "fig7_neighbourhood_demand.png", 6.0),
  B("Unpriced listings are excluded: 66.7% of them have zero open nights in the next year (0% of priced listings), which reflects blocked calendars rather than bookings."),
  B("Demand concentrates in brownstone Brooklyn and parts of lower Manhattan, with two lower-priced Queens neighborhoods in the top 10."),
  B(`Fort Hamilton ranks first, but one host runs ${pct(topH[0].top_host_share)} of its priced listings, so it reflects a single operator.`),
  H2("3.2 Listing types"),
  ...table("Table 5. Demand by stay type and room type (priced listings)",
    ["Stay type", "Room type", "Listings", "Mean open nights", "Reviewed in 12 mo", "Est. occupied nights", "Median price"],
    roomStay.map((r) => [r.stay_type, r.room_type, num(r.listings, 0), num(r.mean_availability_365, 0), pct(r.share_reviewed_12mo), num(r.mean_est_occupied_nights, 0), usd(r.median_price)]),
    [1700, 1900, 1000, 1200, 1300, 1260, 1000], { leftCols: [1] }),
  ...figure("Figure 7. Demand by listing type", "figD1_demand_by_listing_type.png", 6.4),
  B("Short-term entire homes and private rooms show the highest demand. Listings with a 30+ night minimum show far lower estimated occupancy."),
  B("**Compare within a stay type only.** Monthly guests rarely review, and estimated occupancy is derived from reviews, so 30+ night figures are understated."),
  B("Hotel rooms post few reviews on Airbnb and high availability, and their occupancy estimate is the least reliable because many bookings may come through other channels."),
  B(`Among property types, entire guest suites lead both stay types (${num(by(propStay.filter((r) => r.stay_type === "Under 30 nights"), "property_grp", "Entire guest suite").mean_est_occupied_nights, 0)} and ${num(by(propStay.filter((r) => r.stay_type === "30+ nights"), "property_grp", "Entire guest suite").mean_est_occupied_nights, 0)} estimated nights).`),
];

const r4 = [
  H1("4. Pricing Gap Against Comparable Listings"),
  B(`Each listing gets a fair price from a random forest trained on the other four folds, so no listing helps predict itself. Out-of-fold R² is ${num(by(fit, "model", "a").oof_r2_log, 3)}; median error is ${pct(by(fit, "model", "a").median_abs_pct_error)}.`),
  B("Fair price leaves out availability and review counts, so it describes the listing rather than its past sales. It is a typical (median) price, not a mean."),
  B("A gap within ±20% is about the model's normal error and should not be read as mispricing."),
  ...table("Table 6. Listings by gap against fair price", ["Stay type", "More than 20% below", "Within 20%", "More than 20% above"],
    ["Under 30 nights", "30+ nights"].map((s) => [s, gapShare(s, "More than 20% below"), gapShare(s, "Within 20%"), gapShare(s, "More than 20% above")]),
    [3000, 2120, 2120, 2120]),
  ...table("Table 7. Demand and estimated revenue by gap quintile (Q1 = cheapest vs. comparables)",
    ["Stay type", "Quintile", "Median gap", "Mean open nights", "Reviewed in 12 mo", "Est. occupied nights", "Est. annual revenue"],
    gapQ.map((r) => [r.stay_type, `Q${r.gap_quintile}`, signed(Number(r.median_gap) * 100), num(r.mean_availability_365, 0), pct(r.share_reviewed_12mo), num(r.mean_est_occupied_nights, 0), usd(r.mean_est_revenue_365)]),
    [1800, 900, 1100, 1300, 1300, 1460, 1500], { leftCols: [1], size: 18 }),
  ...figure("Figure 8. Demand and revenue by price relative to comparables", "figD2_gap_vs_demand.png", 6.5),
  B(`Listings priced higher than comparables are booked less: short-term ${num(q("Under 30 nights", 1).mean_est_occupied_nights, 0)} → ${num(q("Under 30 nights", 5).mean_est_occupied_nights, 0)} nights; 30+ nights ${num(q("30+ nights", 1).mean_est_occupied_nights, 0)} → ${num(q("30+ nights", 5).mean_est_occupied_nights, 0)} nights.`),
  B(`Short-term revenue rises with relative price (${usd(q("Under 30 nights", 1).mean_est_revenue_365)} → ${usd(q("Under 30 nights", 5).mean_est_revenue_365)}): occupancy falls more slowly than price rises.`),
  B(`30+ night revenue stays flat and falls back in Q5 (${usd(q("30+ nights", 4).mean_est_revenue_365)} → ${usd(q("30+ nights", 5).mean_est_revenue_365)}), where the reviewed share drops to ${pct(q("30+ nights", 5).share_reviewed_12mo)}.`),
  B("**Caution:** this is correlation. Q5 listings may have quality the data cannot see, so this does not show that raising a price would raise revenue. Revenue is price × estimated occupancy, not actual earnings."),
  H2("Neighborhood candidates for under-pricing"),
  ...table("Table 8. High demand, low location premium, no dominant host",
    ["Neighborhood", "Borough", "Listings", "Demand index", "Median price", "Location premium", "Top-host share"],
    candidates.map((r) => [r.neighbourhood, r.borough, num(r.listings, 0), num(r.demand_index, 2), usd(r.median_price), signed(Number(r.median_location_premium) * 100, 1), pct(r.top_host_share)]),
    [2100, 1300, 1000, 1200, 1200, 1400, 1160], { leftCols: [1] }),
  ...figure("Figure 9. Location premium vs. demand", "figD3_premium_vs_demand.png", 6.0),
  B("Location premium compares a listing's fair price with and without location information."),
  B("Rule: top quarter of demand index, premium below −5%, and no host with 50% or more of listings."),
  B(`These are leads to check, not proof. Across neighborhoods, demand and premium are almost unrelated (r = 0.11), and the premium may reflect real local factors.`),
];

const r5 = [
  H1("5. Robustness Checks"),
  ...table("Table 9. Random forest error by segment (test set)", ["Segment", "Test listings", "RMSE (log)", "R² within segment", "Median % error"],
    ["Under 30 nights", "30+ nights", "Entire home/apt", "Private room", "Hotel room", "Shared room", "Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"].map(segRow),
    [3000, 1500, 1500, 1680, 1680]),
  ...figure("Figure 10. Prediction error by segment", "figM6_error_by_segment.png", 6.0),
  ...table("Table 10. Separate vs. pooled models by stay type (test R², log price)", ["Stay type", "Separate model", "Pooled model"],
    segModels.map((r) => [r.segment, num(r.separate_r2_log, 3), num(r.pooled_r2_log, 3)]), [4000, 2680, 2680]),
  B("A single pooled model is enough: separate models gain only about 0.01 in R²."),
  B("Weakest spots are small groups: shared rooms (21 test listings) and the Bronx (127 test listings)."),
];

const r6 = [
  H1("6. Limitations"),
  B("One city and one snapshot (September 2026), so seasonal changes are not captured."),
  B("Listed prices, not prices actually paid. Discounts and fees are not included."),
  B("For 30+ night listings, nightly price comes from a monthly quote, so it is not directly a nightly rate."),
  B("35.1% of listings show no price and are excluded from price models, which may bias results toward actively bookable listings."),
  B("Demand is a proxy. Reviews understate monthly stays, and open nights cannot separate bookings from blocked dates. Estimated occupancy and revenue are model-based."),
  B("Observational data supports associations only. Unobserved quality (photos, renovation, view) is not in the model."),
  B("Hyperparameter tuning stopped at grid edges: random forest at the largest trees and depth tried, GBT at the smallest depth, and Elastic Net at the smallest penalty. A wider grid could improve results slightly."),
  B("Spark ran on one machine, so this project demonstrates the pipeline, not cluster-scale performance."),
];

const r7 = [
  H1("7. Evidence for Business Recommendations"),
  ...table("Table 11. Findings and what they could support", ["Audience", "Finding", "Possible recommendation", "Caution"], [
    ["Hosts", `Short-term: higher relative price goes with higher estimated revenue (${usd(q("Under 30 nights", 3).mean_est_revenue_365)} in Q3, ${usd(q("Under 30 nights", 5).mean_est_revenue_365)} in Q5)`, "Hosts priced well below comparables can test small increases", "Correlation only; test gradually"],
    ["Hosts", `30+ nights: Q5 is booked much less (${num(q("30+ nights", 5).mean_est_occupied_nights, 0)} vs. ${num(q("30+ nights", 3).mean_est_occupied_nights, 0)} nights) and revenue falls back`, "Monthly hosts priced far above comparables can review their price", "Monthly occupancy is understated"],
    ["Hosts", `Bedrooms ${signed(coef("bedrooms"))}, shared bath ${signed(coef("shared bath"))}, gym ${signed(coef("amenity: gym"))}`, "Prioritize size and private-bath features over review badges in pricing", "Not causal; building-level features cannot be changed easily"],
    ["Hosts and investors", `Candidates: ${candidates.map((r) => r.neighbourhood).join(", ")}`, "Check these neighborhoods first when looking for under-pricing", "Leads, not proof"],
    ["Guests", `${gapShare("Under 30 nights", "More than 20% above")} of short-term listings cost over 20% more than comparables`, "Compare similar listings before booking", "Unobserved quality may justify some premiums"],
    ["Platform", `Random forest median error ${pct(rf.median_abs_pct_error)}`, "Similar models could support pricing suggestions for hosts", "Needs regular retraining; prices change seasonally"],
    ["City", "80.7% of listings require 30+ nights; 76.5% of priced listings report no license", "Track the 30+ night market as its own segment when reviewing Local Law 18", "One snapshot cannot show the law's causal effect"],
  ], [1200, 3200, 3000, 1960], { leftCols: [1, 2, 3], size: 17, split: true }),
];

const r8 = [
  H1("8. Changes Since the Introduction"),
  ...table("Table 12. Items to update in the final report", ["Item", "In the Introduction", "Use now"], [
    ["Spark driver memory", "6 GB", "12 GB by default; final notebooks ran with 12–32 GB"],
    ["Size features", "Accommodates, bedrooms, beds, bathrooms", "Add shared bath"],
    ["Fort Hamilton top-host share", "64%", `${pct(topH[0].top_host_share)} (priced listings)`],
    ["Woodhaven median price", "$88", `${usd(by(hoods, "neighbourhood", "Woodhaven").median_price)} (Spark approximate median)`],
    ["Neighborhoods in demand analysis", "85 (all listings)", "72 (priced listings)"],
    ["Under-priced neighborhoods", "Elmhurst, Woodhaven", `Candidates: ${candidates.map((r) => r.neighbourhood).join(", ")}`],
    ["Figures", "Figure 5 (demand)", "Use figures/fig7_neighbourhood_demand.png, generated by the notebook"],
  ], [3000, 2800, 3560], { leftCols: [1, 2] }),
  B("*CORRECTIONS.md* in the repository records two analysis errors, how they were found and how they were fixed. The first versions are kept in *outputs/archive/*. This can support the Discussion or Limitations section."),
  H1("Appendix. Tuning Results and Files"),
  ...table("Table A1. Random forest 5-fold CV (RMSE on log price)", ["Trees", "Max depth", "CV RMSE"], cvRF.map((r) => [r.numTrees, r.maxDepth, num(r.cv_rmse_log, 4)]), [3120, 3120, 3120]),
  ...table("Table A2. Gradient-boosted trees 5-fold CV (150 iterations, step size 0.1)", ["Max depth", "CV RMSE"], cvGBT.map((r) => [r.maxDepth, num(r.cv_rmse_log, 4)]), [4680, 4680]),
  ...table("Table A3. Elastic Net 5-fold CV, top 5 of 12 combinations", ["regParam", "elasticNetParam", "CV RMSE"], cvEN.slice(0, 5).map((r) => [r.regParam, r.elasticNetParam, num(r.cv_rmse_log, 4)]), [3120, 3120, 3120]),
  B("Code: *code/02_Modeling_PySpark.ipynb* (models), *code/03_Demand_and_Pricing_Gap.ipynb* (listing-type demand, pricing gap)."),
  B("Saved models: *models.zip* in the models-v1 release of the project repository. Rerun instructions are in *README.md*."),
];

const doc = new Document({
  title: "Results Package",
  styles: {
    default: { document: { run: { font: "Calibri", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: "Calibri", color: "1C5CAB" }, paragraph: { spacing: { before: 320, after: 120 }, outlineLevel: 0, keepNext: true } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Calibri" }, paragraph: { spacing: { before: 220, after: 80 }, outlineLevel: 1, keepNext: true } },
    ],
  },
  numbering: { config: [{ reference: "bullets", levels: [
    { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 240 } } } },
  ] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 18 })] })] }) },
    children: [...title, ...r1, ...r2, ...r3, ...r4, ...r5, ...r6, ...r7, ...r8],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = path.join(ROOT, "Results_Package_Final_Report.docx");
  fs.writeFileSync(out, buf);
  console.log("wrote", path.basename(out));
});
