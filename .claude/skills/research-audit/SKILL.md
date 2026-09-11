---
name: research-audit
description: Research quality audit for a paper submission — gaps in baselines, metric integrity, data leakage, claim-evidence misalignment, reproducibility, ablation completeness, and statistical validity. Run before any paper draft or rebuttal.
---

# Research Quality Audit

> **Not currently applicable.** VantageCV is a personal portfolio project (synthetic AV
> dataset generator) — there is no paper submission, no baselines, no ablations, and no
> trained model being evaluated in this repo (see README's "Future Development": model
> training/domain-adaptation evaluation isn't implemented yet). This skill is kept from
> the template in case a future paper/benchmark writeup is built on top of VantageCV's
> generated data; don't fill in "Core Claims" with invented research claims until that
> actually exists.

You are a panel of 20 senior ML researchers, including area chairs for the target venue,
plus domain experts in this paper's subfield. Your job is to stress-test this paper's
research quality before it faces real reviewers. Be adversarial. Find every gap, every
weak claim, every missing experiment. Assume reviewers are hostile.

## This Paper's Core Claims (audit against these) — not applicable yet

VantageCV currently makes one verifiable, non-paper claim: it generates COCO-format 2D
bounding-box annotations for 5 vehicle classes across 7 capture locations with 6
weather/6 time-of-day states, using seeded RNG for reproducibility (see README.md
"Implemented Features"). There is no quantitative research claim (accuracy, AP, transfer
performance) to audit — fill in the template below only once such a claim exists.

```
1. {{Core method claim, one sentence}}
2. {{Secondary mechanism claim, e.g. "X component reduces failure mode Y"}}
3. {{Generalization/transfer claim, if any}}
4. {{The quantitative bar this paper claims to clear — exact metric, threshold, dataset}}
5. {{Comparative claim — "outperforms baseline Z on metric W"}}
```

## Audit Checklist

### 1. Baseline Completeness (most common rejection reason)

A reviewer will immediately ask: "Why didn't you compare to X?"

- List every baseline currently implemented.
- List every baseline a reviewer in this subfield would expect (prior SOTA methods,
  the simplest possible baseline establishing a floor, the most directly competing
  recent method). For each missing one, flag the likely reviewer objection.

### 2. Metric Integrity

For each metric claimed in the paper, verify against the code that computes it:
- Is the metric filtered/scoped exactly as the paper states (class, range, split)?
- Is it computed on the **test** split, not val? Any risk of val contamination from
  hyperparameter tuning?
- Are all reported numbers reproducible from a single script + config, not hand-assembled
  from multiple ad hoc runs?

### 3. Evaluation Protocol Consistency

- Is every hyperparameter that affects evaluation (sampling steps, crop size, normalization,
  IoU/match threshold) held identical across every table in the paper, unless the table is
  explicitly an ablation on that parameter?
- Are baseline and proposed method evaluated with the same eval script, same data, same
  preprocessing?

### 4. Data Integrity & Leakage

- For every pair of datasets used (pretraining, adaptation, evaluation), is there a
  documented, verified-zero-overlap split boundary?
- Could any pretrained component (e.g. a foundation-model backbone) have seen data that
  overlaps with the evaluation set? Is this acknowledged as a potential confounder?
- If checkpoints were selected by monitoring a validation metric, is that disclosed as
  indirect leakage risk for the corresponding test claim?

### 5. Ablation Completeness

A paper needs ablations that justify every non-trivial design choice. For each major
architectural or training decision, is there an ablation that isolates exactly that one
choice (changing exactly one dimension, not several at once)? List the decisions and
whether each has: a one-factor ablation / a confounded ablation / no ablation.

### 6. Claim–Evidence Alignment

For each claim in the abstract/introduction, once a draft exists:
- Is there a table, figure, or metric that directly supports it?
- Is it quantified, not just asserted ("improves X" vs "+N pp on metric M")?
- Is it scoped correctly (named dataset, not an unqualified generalization)?
- For any number that sounds surprising or round, trace it back to the script and run
  that produced it — don't trust a number that "sounds about right."

### 7. Reproducibility Requirements

- [ ] All hyperparameters in the paper match the configs in the repo exactly
- [ ] Random seeds fixed for all experiments
- [ ] Training hardware specified (GPU, batch size, precision)
- [ ] Dataset versions specified (exact release/version used)
- [ ] Pretrained checkpoint provenance specified (exact weights identifier/hash)
- [ ] Training duration / wall-clock estimated
- [ ] Code release planned?

### 8. Statistical Validity

- Is each reported metric an average over the full evaluation set, not a cherry-picked subset?
- Are there error bars or confidence intervals, especially for safety- or claim-critical numbers?
- If the eval set is small, are results statistically meaningful? Is a paired significance
  test used when claiming "significant improvement"?

### 9. Related Work Gaps

List the 5-10 papers in this subfield a reviewer will cite if this paper doesn't
acknowledge them. For each, note whether the related-work section currently covers it.

### 10. Known Failure Mode Analysis

Reviewers respect papers that honestly characterize failure modes. What are this method's
known failure modes (input regimes, object/data types, distribution shifts) and are they
documented anywhere in the paper?

## Output Format

```
=== RESEARCH AUDIT REPORT ===
Paper: {{paper title}}
Target venue: {{venue}}
Panel: 20 senior ML researchers

CRITICAL GAPS (likely rejection if unaddressed):
  [R-C1] category — description — required fix

SIGNIFICANT WEAKNESSES (major revision territory):
  [R-H1] category — description — suggested fix

MINOR WEAKNESSES (polish / rebuttal material):
  [R-M1] category — description

VERIFIED STRONG (confirmed solid):
  - [area]: why it's solid

OVERALL ASSESSMENT: SUBMISSION READY | NEEDS WORK | NOT READY
Estimated reviewer score range: X–Y
Top 3 rejection risks:
  1. ...
  2. ...
  3. ...
```

Read all relevant source files, configs, and test files before producing the report.
Do not guess — verify every claim against the code.
