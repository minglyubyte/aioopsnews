import { localizePublicCategory } from "./publicDashboardLocalization";
import {
  topicSlugFromValue,
  type TopicKind,
} from "./publicTopicRoutes";
import type { ReaderLocale } from "./locale";

type TopicDefinition = {
  description: Record<ReaderLocale, string>;
  title: Record<ReaderLocale, string>;
  value: string;
};

const CATEGORY_TOPICS: TopicDefinition[] = [
  {
    value: "Hallucinations",
    title: {
      en: "AI Hallucination Incidents",
      zh: "AI 幻觉事件",
    },
    description: {
      en: "Browse verified and source-backed AI hallucination incidents, including fake citations, fabricated facts, and model outputs that looked plausible but failed in public.",
      zh: "浏览已验证或有来源支撑的 AI 幻觉事件，包括虚假引用、捏造事实，以及看似可信但在公共场景中失败的模型输出。",
    },
  },
  {
    value: "Autonomous Systems",
    title: {
      en: "Autonomous Systems AI Incidents",
      zh: "自主系统 AI 事件",
    },
    description: {
      en: "Track AI incidents involving autonomous vehicles, robots, and automated systems where perception, planning, or operational controls failed.",
      zh: "追踪涉及自动驾驶车辆、机器人和自动化系统的 AI 事件，关注感知、规划或运营控制失效。",
    },
  },
  {
    value: "Model Governance",
    title: {
      en: "AI Model Governance Incidents",
      zh: "AI 模型治理事件",
    },
    description: {
      en: "Review cases where AI deployment, oversight, policy, or risk controls failed to prevent real-world harm or public correction.",
      zh: "查看 AI 部署、监督、政策或风险控制未能阻止现实影响或公开纠正的案例。",
    },
  },
  {
    value: "Privacy/Security",
    title: {
      en: "AI Privacy and Security Incidents",
      zh: "AI 隐私与安全事件",
    },
    description: {
      en: "Browse AI incidents involving data leakage, privacy failures, security issues, and sensitive information exposed through automated systems.",
      zh: "浏览涉及数据泄露、隐私失败、安全问题，以及自动化系统暴露敏感信息的 AI 事件。",
    },
  },
  {
    value: "Job Automation Fails",
    title: {
      en: "AI Job Automation Failures",
      zh: "AI 岗位自动化失灵事件",
    },
    description: {
      en: "Explore incidents where AI automation failed in workplace, hiring, support, or business processes.",
      zh: "探索 AI 自动化在工作、招聘、支持或业务流程中失效的事件。",
    },
  },
  {
    value: "Missed Timelines",
    title: {
      en: "AI Missed Timeline Incidents",
      zh: "AI 延期失约事件",
    },
    description: {
      en: "Track AI claims and deployments where promised timelines, capabilities, or outcomes did not materialize as expected.",
      zh: "追踪 AI 承诺、部署或能力未按预期时间线兑现的事件。",
    },
  },
];

const SOURCE_TOPICS: TopicDefinition[] = [
  sourceTopic(
    "legal_hallucination",
    "AI Legal Hallucination Cases",
    "AI 法律幻觉案例",
  ),
  sourceTopic(
    "autonomous_vehicle",
    "AI Autonomous Vehicle Incidents",
    "AI 自动驾驶事件",
  ),
  sourceTopic("coding_failure", "AI Coding Failure Incidents", "AI 代码生成故障"),
  sourceTopic(
    "security_privacy",
    "AI Security and Privacy Incidents",
    "AI 安全与隐私事件",
  ),
  sourceTopic(
    "customer_support",
    "AI Customer Support Incidents",
    "AI 客户支持事件",
  ),
  sourceTopic(
    "healthcare_benefits",
    "AI Healthcare and Benefits Incidents",
    "AI 医疗与福利事件",
  ),
  sourceTopic(
    "education_public_sector",
    "AI Public Sector and Education Incidents",
    "AI 公共部门与教育事件",
  ),
  sourceTopic("model_governance", "AI Model Governance Cases", "AI 模型治理案例"),
  sourceTopic("other", "Other AI Incidents", "其他 AI 事件"),
];

export function getTopicDefinition(kind: TopicKind, slug: string) {
  return topicDefinitions(kind).find(
    (topic) => topicSlugFromValue(topic.value) === slug,
  );
}

export function topicDefinitions(kind: TopicKind) {
  return kind === "category" ? CATEGORY_TOPICS : SOURCE_TOPICS;
}

export function topicDisplayLabel(
  kind: TopicKind,
  value: string,
  locale: ReaderLocale,
) {
  if (kind === "category") {
    return localizePublicCategory(value, locale);
  }

  return getTopicDefinition(kind, topicSlugFromValue(value))?.title[locale] ?? value;
}

function sourceTopic(
  value: string,
  englishTitle: string,
  chineseTitle: string,
): TopicDefinition {
  return {
    value,
    title: {
      en: englishTitle,
      zh: chineseTitle,
    },
    description: {
      en: `Browse verified and source-backed ${englishTitle.toLowerCase()} from the public AI incident archive.`,
      zh: `浏览公开 AI 事件档案中已验证或有来源支撑的${chineseTitle}。`,
    },
  };
}
