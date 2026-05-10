import {
  buildIncidentDisplayTitle,
  buildOriginalIncidentTitle,
} from "../lib/publicIncidentTitleCore.js";
import type { PublicIncidentBase } from "../types/incident";

function buildIncident(
  overrides: Partial<PublicIncidentBase> = {},
): PublicIncidentBase {
  return {
    id: overrides.id ?? "incident-1",
    headline:
      overrides.headline ??
      "Legal filing: Damien Charlotin's AI hallucination tracker records Amanda Adams v. Allen Butler Construction, Inc. in CA Texas with Pro Se Litigant linked to alleged or found AI legal hallucination. Nature: Fabricated: Case Law | Appellant cited several cases that do not exist.",
    headline_en:
      overrides.headline_en ??
      overrides.headline ??
      "Legal filing: Damien Charlotin's AI hallucination tracker records Amanda Adams v. Allen Butler Construction, Inc. in CA Texas with Pro Se Litigant linked to alleged or found AI legal hallucination. Nature: Fabricated: Case Law | Appellant cited several cases that do not exist.",
    headline_zh:
      overrides.headline_zh ??
      "法律诉讼：Damien Charlotin的AI幻觉追踪器记录Amanda Adams诉Allen Butler Construction, Inc.案，德克萨斯州法院，涉诉人自称与涉嫌或已发现的AI法律幻觉有关。性质：捏造：判例法 | 上诉人引用了多个不存在的案例。",
    date_logged: "2026-05-05",
    company_involved: "Legal filing",
    company_involved_zh: "法律诉讼",
    categories: ["Hallucinations"],
    severity_score: 3,
    status: "approved",
    publication_track: "verified_accident",
    evidence_tier: "court_or_regulator",
    source_family: "legal_hallucination",
    verification_summary:
      "Fixed verified source documents this legal hallucination.",
    ...overrides,
  };
}

describe("public incident display titles", () => {
  it("uses a readable case-name title for Damien Charlotin legal hallucination records", () => {
    const incident = buildIncident();

    expect(buildIncidentDisplayTitle(incident, "en")).toBe(
      "AI legal hallucination: Amanda Adams v. Allen Butler Construction, Inc.",
    );
    expect(buildIncidentDisplayTitle(incident, "zh")).toBe(
      "AI 法律幻觉：Amanda Adams v. Allen Butler Construction, Inc.",
    );
  });

  it("uses the final Chinese lawsuit separator when court names contain 诉", () => {
    const incident = buildIncident({
      headline_zh:
        "法律诉讼：达米安·夏洛坦的AI幻觉追踪器记录俄勒冈州上诉法院Boersma诉Davenport案，涉诉自诉人使用AI法律幻觉。结果：金钱制裁。",
    });

    expect(buildIncidentDisplayTitle(incident, "zh")).toBe(
      "AI 法律幻觉：Boersma v. Davenport",
    );
  });

  it("trims English titles to 14 words and at most 90 graphemes", () => {
    const incident = buildIncident({
      source_family: "model_governance",
      headline_en:
        "Warehouse classifier reroutes urgent medical inventory after deployment and creates cascading fulfillment delays across regional facilities",
      headline_zh: null,
    });
    const title = buildIncidentDisplayTitle(incident, "en");

    expect(title).toBe(
      "Warehouse classifier reroutes urgent medical inventory after deployment and creates...",
    );
    expect(Array.from(title).length).toBeLessThanOrEqual(90);
  });

  it("trims Chinese titles to at most 52 graphemes", () => {
    const incident = buildIncident({
      source_family: "model_governance",
      headline_zh:
        "某公司客服机器人在上线后连续向用户展示内部备注并错误发送敏感账户信息导致隐私风险扩大需要人工紧急回滚并引发监管调查与客户投诉",
    });
    const title = buildIncidentDisplayTitle(incident, "zh");

    expect(title).toBe(
      "某公司客服机器人在上线后连续向用户展示内部备注并错误发送敏感账户信息导致隐私风险扩大需要人工紧急回...",
    );
    expect(Array.from(title)).toHaveLength(52);
  });

  it("keeps the original localized title available for detail disclosure", () => {
    const incident = buildIncident({
      headline_en: "Short English title",
      headline_zh: "中文原始标题",
    });

    expect(buildOriginalIncidentTitle(incident, "en")).toBe(
      "Short English title",
    );
    expect(buildOriginalIncidentTitle(incident, "zh")).toBe("中文原始标题");
  });
});
