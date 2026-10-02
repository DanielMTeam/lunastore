"""Management command to benchmark AI moderation models (Jev vs DeepSeek) for LunaStore reviews."""

import json
import logging
import random
import statistics
import time
from typing import Any

from constance import config
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.marketplace.services.ai_moderation import moderate_review_text

logger = logging.getLogger(__name__)

# Representative golden dataset for retro software reviews
BENCHMARK_CASES = [
    # --- Category: Clear Approvals (Valid feedback, praises, bug reports) ---
    {
        "id": "appr_1",
        "category": "approval",
        "expected_action": "approved",
        "app_title": "Foobar2000 Retro",
        "text": "Отличный плеер! Воспроизводит FLAC на Windows XP SP3 без тормозов, звук чистый.",
    },
    {
        "id": "appr_2",
        "category": "approval",
        "expected_action": "approved",
        "app_title": "Total Commander 7.5",
        "text": "Программа вылетает при копировании больших файлов на Win2000. Надеюсь, разработчик исправит.",
    },
    {
        "id": "appr_3",
        "category": "approval",
        "expected_action": "approved",
        "app_title": "WinRAR 3.93",
        "text": "Мне не очень понравился новый скин интерфейса, старый был привычнее. Ставлю 3 звезды.",
    },
    {
        "id": "appr_4",
        "category": "approval",
        "expected_action": "approved",
        "app_title": "RetroArch XP",
        "text": "Does this build support Windows 98 SE with KernelEx, or only WinXP? Great software nonetheless.",
    },
    {
        "id": "appr_5",
        "category": "approval",
        "expected_action": "approved",
        "app_title": "Miranda IM",
        "text": "Спасибо автору за сборку! Все протоколы подключились сразу, потребляет всего 12 мегабайт ОЗУ.",
    },
    {
        "id": "appr_6",
        "category": "approval",
        "expected_action": "approved",
        "app_title": "K-Lite Mega Codec Pack",
        "text": "После установки перестало воспроизводиться видео формата avi. Пришлось откатиться на старую версию.",
    },
    {
        "id": "appr_7",
        "category": "approval",
        "expected_action": "approved",
        "app_title": "7-Zip 9.20",
        "text": "Быстро распаковывает архивы на старом Celeron 600. Незаменимая утилита для любой ретро-машины.",
    },
    {
        "id": "appr_8",
        "category": "approval",
        "expected_action": "approved",
        "app_title": "AIMP 2",
        "text": "Работает стабильно, обложки ретро-стиля Windows XP смотрятся шикарно. 5 звёзд без сомнений.",
    },
    {
        "id": "appr_9",
        "category": "approval",
        "expected_action": "approved",
        "app_title": "Notepad++ XP",
        "text": "Не хватает поддержки подсветки для редких старых форматов файлов, но для базового кода отлично.",
    },
    {
        "id": "appr_10",
        "category": "approval",
        "expected_action": "approved",
        "app_title": "Opera 12 Presto",
        "text": "Классика интернета нулевых. Конечно, современный веб тормозит, но ретро-сайты открывает моментально.",
    },

    # --- Category: Clear Auto-Rejections (Insults, profanity, spam, phishing) ---
    {
        "id": "rej_1",
        "category": "rejection",
        "expected_action": "rejected",
        "app_title": "DriverPack XP",
        "text": "Автор конченый урод и пи*орас, софт полное говно, убейся об стену мразь.",
    },
    {
        "id": "rej_2",
        "category": "rejection",
        "expected_action": "rejected",
        "app_title": "AnyApp",
        "text": "СКАЧАТЬ БЕСПЛАТНО КЛЮЧИ И ВЗЛОМ В ТЕЛЕГРАМ: https://t.me/free_keys_winxp_hack",
    },
    {
        "id": "rej_3",
        "category": "rejection",
        "expected_action": "rejected",
        "app_title": "Cleaner Pro",
        "text": "Earn 500$ daily with crypto bot! Join our chat now bit.ly/scam-win-money guaranteed fast payouts.",
    },
    {
        "id": "rej_4",
        "category": "rejection",
        "expected_action": "rejected",
        "app_title": "Retro Game",
        "text": "Ты сдохнешь гнида, найду тебя в реале и переломаю руки за то что комп сломал вирус твой.",
    },
    {
        "id": "rej_5",
        "category": "rejection",
        "expected_action": "rejected",
        "app_title": "SpeedUp XP",
        "text": "Казино Вулкан дарит 100 фриспинов при регистрации! Переходи по ссылке http://vulkan-slots-win.ru",
    },
    {
        "id": "rej_6",
        "category": "rejection",
        "expected_action": "rejected",
        "app_title": "Player",
        "text": "Ебать вы дауны тупые, создатели этого сайта хуесосы безмозглые.",
    },
    {
        "id": "rej_7",
        "category": "rejection",
        "expected_action": "rejected",
        "app_title": "XP Theme Pack",
        "text": "FREE STEAM WALLET CODES GENERATOR 2026 WORKING CLICK HERE http://free-steam-cards-generator.xyz",
    },
    {
        "id": "rej_8",
        "category": "rejection",
        "expected_action": "rejected",
        "app_title": "Utility",
        "text": "Пошёл на х*й со своей парашей еб*ной, чтоб у тебя руки отсохли.",
    },

    # --- Category: Borderline / Manual Moderation (Borderline flame, ambiguous links, sarcasm) ---
    {
        "id": "bord_1",
        "category": "borderline",
        "expected_action": "pending",
        "app_title": "Office XP Tools",
        "text": "Разработчик видимо под веществами сидел когда верстал это меню, иначе такой бред не объяснить.",
    },
    {
        "id": "bord_2",
        "category": "borderline",
        "expected_action": "pending",
        "app_title": "Old Browser",
        "text": "Кому вообще нужна эта старая рухлядь в 2026 году? Выкиньте этот хлам на помойку и не позорьтесь.",
    },
    {
        "id": "bord_3",
        "category": "borderline",
        "expected_action": "pending",
        "app_title": "DirectX 9 Patch",
        "text": "Инструкцию по установке и рабочий фикс dll выложил у себя на форуме forum.retro-os.org/topic-33",
    },
    {
        "id": "bord_4",
        "category": "borderline",
        "expected_action": "pending",
        "app_title": "TweakUI XP",
        "text": "Антивирус Avast ругается на троян в установщике. Это ложная тревога или вирусня реально?",
    },
    {
        "id": "bord_5",
        "category": "borderline",
        "expected_action": "pending",
        "app_title": "File Manager",
        "text": "Кряк и регистрационный ключ можно взять на рутрекере в раздаче от 2008 года.",
    },
    {
        "id": "bord_6",
        "category": "borderline",
        "expected_action": "pending",
        "app_title": "System Monitor",
        "text": "А в т о р д у р а к и л о х, ничего не работает.",
    },
]


class Command(BaseCommand):
    help = "Benchmark AI review moderation accuracy, latency, and costs (Jev vs DeepSeek via OpenRouter)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            default="typesafe/jev-router",
            help="Primary OpenRouter model to test (default: typesafe/jev-router)",
        )
        parser.add_argument(
            "--compare",
            action="store_true",
            help="Run comparative benchmark between Jev Router and DeepSeek V4.1 Flash",
        )
        parser.add_argument(
            "--api-key",
            type=str,
            default="",
            help="OpenRouter API key (overrides settings/constance)",
        )
        parser.add_argument(
            "--mock",
            action="store_true",
            help="Simulate responses offline with realistic latency and score distributions (0 tokens)",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="",
            help="Path to save benchmark JSON report (e.g. benchmark_report.json)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print detailed results for every test case",
        )

    def handle(self, *args, **options):
        primary_model = options["model"]
        compare_mode = options["compare"]
        api_key = options["api_key"] or getattr(config, "OPENROUTER_API_KEY", "") or getattr(settings, "OPENROUTER_API_KEY", "")
        is_mock = options["mock"]
        output_file = options["output"]
        verbose = options["verbose"]

        models_to_run = [primary_model]
        if compare_mode:
            secondary_model = "deepseek/deepseek-v4.1-flash"
            if secondary_model not in models_to_run:
                models_to_run.append(secondary_model)

        self.stdout.write(self.style.SUCCESS("=" * 78))
        self.stdout.write(self.style.SUCCESS("  LunaStore AI Review Moderation Benchmark Suite"))
        self.stdout.write(self.style.SUCCESS("=" * 78))
        self.stdout.write(f"- Dataset size: {len(BENCHMARK_CASES)} cases")
        self.stdout.write(f"- Models: {', '.join(models_to_run)}")
        self.stdout.write(f"- Mode: {'OFFLINE MOCK (0 tokens spent)' if is_mock else 'LIVE OPENROUTER API'}\n")

        if not is_mock and not api_key:
            self.stdout.write(self.style.ERROR("Error: OPENROUTER_API_KEY is not configured and --api-key was not provided."))
            self.stdout.write(self.style.WARNING("Tip: Run with --mock for offline testing without API key."))
            return

        all_results: dict[str, Any] = {}

        for model in models_to_run:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n[*] Evaluating model: {model}..."))
            stats = self._run_model_evaluation(
                model=model,
                api_key=api_key,
                is_mock=is_mock,
                verbose=verbose,
            )
            all_results[model] = stats
            self._print_model_summary(model, stats)

        if compare_mode and len(models_to_run) >= 2:
            self._print_comparison(all_results)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"\n[+] Full report saved to: {output_file}"))

    def _simulate_mock_response(self, model: str, case: dict) -> tuple[float, str, list[str], str, float, int]:
        """Simulate realistic latency and verdict distributions for offline testing."""
        expected = case["expected_action"]
        is_jev = "jev" in model.lower()

        # Simulated latency: Jev is faster (80-280ms), DeepSeek slightly slower (350-900ms)
        if is_jev:
            latency = random.uniform(85.0, 290.0)
        else:
            latency = random.uniform(320.0, 850.0)

        tokens = len(case["text"]) // 4 + 75

        if expected == "approved":
            score = round(random.uniform(0.01, 0.18), 2)
            decision = "approved"
            flags = []
            reason = "Constructive user feedback"
        elif expected == "rejected":
            score = round(random.uniform(0.85, 0.99), 2)
            decision = "rejected"
            flags = ["insult", "profanity"] if "урод" in case["text"] or "мразь" in case["text"] else ["spam"]
            reason = "Insult or spam detected"
        else:  # pending
            score = round(random.uniform(0.40, 0.70), 2)
            decision = "pending"
            flags = ["flame"]
            reason = "Requires manual context check"

        return score, decision, flags, reason, latency, tokens

    def _run_model_evaluation(
        self,
        model: str,
        api_key: str,
        is_mock: bool,
        verbose: bool,
    ) -> dict[str, Any]:
        latencies: list[float] = []
        total_tokens = 0
        correct_count = 0
        false_positives = 0  # Approved review marked as rejected
        false_negatives = 0  # Toxic/spam review marked as approved
        valid_json_count = 0

        case_results = []

        for case in BENCHMARK_CASES:
            case_id = case["id"]
            expected = case["expected_action"]

            if is_mock:
                score, decision, flags, reason, latency, tokens = self._simulate_mock_response(model, case)
                valid_json = True
            else:
                from constance.test import override_config
                try:
                    with override_config(OPENROUTER_API_KEY=api_key):
                        res = moderate_review_text(
                            text=case["text"],
                            app_title=case["app_title"],
                            model_override=model,
                            timeout_override=10.0,
                            disable_fallback=True,
                        )
                    score = res.score if res.score is not None else 0.5
                    decision = res.decision
                    flags = res.flags
                    reason = res.reason or (res.error if res.error else "")
                    latency = res.latency_ms
                    used_tokens = res.tokens_used.get("total_tokens") if isinstance(res.tokens_used, dict) else None
                    tokens = int(used_tokens) if used_tokens is not None else (len(case["text"]) // 4 + 75)
                    valid_json = res.raw_response is not None
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f"  [!] Error processing {case_id}: {exc}"))
                    score = 0.5
                    decision = "pending"
                    flags = []
                    reason = str(exc)
                    latency = 0.0
                    tokens = len(case["text"]) // 4 + 75
                    valid_json = False

            latencies.append(latency)
            total_tokens += tokens
            if valid_json:
                valid_json_count += 1

            is_match = (decision == expected)
            if is_match:
                correct_count += 1

            if expected == "approved" and decision == "rejected":
                false_positives += 1
            elif expected == "rejected" and decision == "approved":
                false_negatives += 1

            if verbose:
                status_color = self.style.SUCCESS if is_match else self.style.ERROR
                self.stdout.write(
                    f"  [{case_id}] {status_color(decision.upper())} (expected: {expected}) "
                    f"| score: {score:.2f} | {latency:.0f}ms | {case['text'][:40]}..."
                )

            case_results.append({
                "id": case_id,
                "text": case["text"],
                "expected": expected,
                "actual": decision,
                "score": score,
                "flags": flags,
                "reason": reason,
                "latency_ms": round(latency, 1),
                "is_match": is_match,
            })

        latencies.sort()
        count = len(latencies)
        avg_lat = statistics.mean(latencies) if latencies else 0
        p50 = latencies[int(count * 0.50)] if latencies else 0
        p90 = latencies[int(count * 0.90)] if latencies else 0
        p95 = latencies[int(count * 0.95)] if latencies else 0

        # Cost calculation based on OpenRouter Jev pricing ($0.042 / 1M prompt tokens)
        cost_per_million = 0.042 if "jev" in model.lower() else 0.14
        estimated_cost_1k = (total_tokens / len(BENCHMARK_CASES)) * 1000 / 1_000_000 * cost_per_million

        accuracy = (correct_count / count) * 100.0 if count else 0.0
        json_conform = (valid_json_count / count) * 100.0 if count else 0.0

        return {
            "model": model,
            "total_cases": count,
            "accuracy_pct": round(accuracy, 1),
            "json_conformance_pct": round(json_conform, 1),
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "latency": {
                "avg_ms": round(avg_lat, 1),
                "min_ms": round(min(latencies), 1) if latencies else 0,
                "max_ms": round(max(latencies), 1) if latencies else 0,
                "p50_ms": round(p50, 1),
                "p90_ms": round(p90, 1),
                "p95_ms": round(p95, 1),
            },
            "estimated_cost_per_1k_reviews_usd": round(estimated_cost_1k, 6),
            "cases": case_results,
        }

    def _print_model_summary(self, model: str, stats: dict[str, Any]):
        lat = stats["latency"]
        self.stdout.write(f"\n--- Evaluation Results for {model} ---")
        self.stdout.write(f"- Decision Accuracy:          {stats['accuracy_pct']}% ({stats['total_cases']} cases)")
        self.stdout.write(f"- JSON Schema Conformance:    {stats['json_conformance_pct']}%")
        self.stdout.write(f"- False Positives (over-ban): {stats['false_positives']}")
        self.stdout.write(f"- False Negatives (leakage):  {stats['false_negatives']}")
        self.stdout.write(
            f"- Latency:                    Avg: {lat['avg_ms']}ms | P50: {lat['p50_ms']}ms | "
            f"P90: {lat['p90_ms']}ms | Max: {lat['max_ms']}ms"
        )
        self.stdout.write(f"- Estimated Cost per 1k reviews: ${stats['estimated_cost_per_1k_reviews_usd']:.5f} USD")

    def _print_comparison(self, results: dict[str, Any]):
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 84))
        self.stdout.write(self.style.SUCCESS("  Comparative Summary Table (Jev vs DeepSeek)"))
        self.stdout.write(self.style.SUCCESS("=" * 84))
        header = f"{'Model':<32} | {'Accuracy':<8} | {'P50 Latency':<12} | {'P90 Latency':<12} | {'Cost/1k':<10}"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        for model_name, s in results.items():
            line = (
                f"{model_name:<32} | "
                f"{s['accuracy_pct']:>6.1f}% | "
                f"{s['latency']['p50_ms']:>8.1f}ms | "
                f"{s['latency']['p90_ms']:>8.1f}ms | "
                f"${s['estimated_cost_per_1k_reviews_usd']:.5f}"
            )
            self.stdout.write(line)
        self.stdout.write("=" * 84)
