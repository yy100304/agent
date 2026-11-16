"""结果验证器：规则层（结构校验）+ LLM 层（质量评分），输出反馈驱动 Self-Loop."""
from typing import Optional

from pydantic import BaseModel

from app.agents.base import AgentProfile, ValidationResult
from app.core.config import settings
from app.services.llm_service import llm_service


class _LLMScore(BaseModel):
    """LLM 质量评分的结构化输出."""

    score: float  # 0~1
    feedback: str = ""


class OutputValidator:
    """对子 Agent 输出做双重验证.

    - 规则层（无 LLM 依赖，Demo 稳定基线）：
      非空 / 最短长度 / 结构关键词（如 Tutor 必须含「定义」「举例」）
    - LLM 层（可选增强）：对学生需求的相关性与质量打分，低于阈值给反馈
    """

    SCORE_THRESHOLD = 0.55

    def validate(
        self, profile: AgentProfile, output: str, message: str
    ) -> ValidationResult:
        checks: list[dict] = []

        # ---- 规则层 ----
        ok_len = len(output.strip()) >= profile.min_output_chars
        checks.append({"name": "长度检查", "passed": ok_len,
                       "detail": f"{len(output.strip())} 字符（要求 ≥{profile.min_output_chars}）"})

        ok_struct = True
        struct_detail = "结构关键词齐全"
        if profile.structure_keywords:
            missing = [kw for kw in profile.structure_keywords if kw not in output]
            ok_struct = not missing
            struct_detail = (
                "结构关键词齐全" if ok_struct else f"缺少结构区块：{'、'.join(missing)}"
            )
        checks.append({"name": "结构检查", "passed": ok_struct, "detail": struct_detail})

        if not (ok_len and ok_struct):
            feedback = (
                f"输出未通过规则校验（{struct_detail if not ok_struct else '内容过短'}），"
                "请严格按输出模板补全结构后重新生成。"
            )
            return ValidationResult(passed=False, score=None, feedback=feedback, checks=checks)

        # ---- LLM 层（可选，默认关闭以降低单次对话延迟）----
        if settings.AGENT_LLM_VALIDATION and llm_service.available:
            llm_result = self._llm_score(profile, output, message)
            if llm_result is not None:
                score, feedback = llm_result
                checks.append({"name": "质量评分", "passed": score >= self.SCORE_THRESHOLD,
                               "detail": f"LLM 评分 {score:.2f}（阈值 {self.SCORE_THRESHOLD}）"})
                if score < self.SCORE_THRESHOLD:
                    return ValidationResult(
                        passed=False, score=score,
                        feedback=feedback or "输出与用户需求相关性不足，请针对性重写。",
                        checks=checks,
                    )
                return ValidationResult(passed=True, score=score, checks=checks)

        # 规则全过 + LLM 不可用 → 通过
        return ValidationResult(passed=True, score=None, checks=checks)

    def _llm_score(
        self, profile: AgentProfile, output: str, message: str
    ) -> Optional[tuple[float, str]]:
        prompt = (
            f"你是输出质量评审员。子智能体「{profile.name}」收到了用户请求并输出了结果。\n"
            f"用户请求：{message}\n"
            f"子智能体输出：\n{output[:2000]}\n"
            "请评估该输出对学生用户的质量与相关性（0~1 分，0.6 及格）。"
            '只输出 JSON：{"score": 0~1的小数, "feedback": "一句话改进意见（高分时可为空）"}'
        )
        result = llm_service.structured_output(
            [{"role": "user", "content": prompt}], _LLMScore, temperature=0.0
        )
        if result is None:
            return None
        score = max(0.0, min(result.score, 1.0))
        return score, result.feedback


output_validator = OutputValidator()
