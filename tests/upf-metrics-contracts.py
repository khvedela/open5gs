#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def require(content: str, token: str, source: str) -> None:
    if token not in content:
        raise AssertionError(f"{source} is missing required contract token: {token}")


def require_guarded_counter(content: str, counter: str) -> None:
    increment = re.search(
        rf"upf_metrics_inst_global_inc\(\s*{counter}\s*\);",
        content,
    )
    if increment is None:
        raise AssertionError(f"src/upf/gtp-path.c does not increment {counter}")
    increment_at = increment.start()

    guard = "if (ogs_metrics_self()->data_plane_packet_counters)"
    guard_at = content.rfind(guard, 0, increment_at)
    if guard_at < 0 or increment_at - guard_at > 160:
        raise AssertionError(f"{counter} is not protected by the opt-in metrics guard")
    if "#if 0" in content[guard_at:increment_at]:
        raise AssertionError(f"{counter} is still compiled out")


def main() -> int:
    metrics_context_header = read("lib/metrics/context.h")
    metrics_context = read("lib/metrics/context.c")
    upf_metrics = read("src/upf/metrics.c")
    upf_gtp = read("src/upf/gtp-path.c")
    upf_init = read("src/upf/init.c")
    upf_config = read("configs/open5gs/upf.yaml.in")

    require(
        metrics_context_header,
        "bool        data_plane_packet_counters;",
        "lib/metrics/context.h",
    )
    require(
        metrics_context,
        "self.data_plane_packet_counters = false;",
        "lib/metrics/context.c",
    )
    require(
        metrics_context,
        '"data_plane_packet_counters"',
        "lib/metrics/context.c",
    )
    require(
        metrics_context,
        "ogs_yaml_iter_bool(&metrics_iter)",
        "lib/metrics/context.c",
    )
    require(
        upf_config,
        "data_plane_packet_counters: false",
        "configs/open5gs/upf.yaml.in",
    )
    require(
        upf_init,
        "N3 data-plane packet counters are enabled",
        "src/upf/init.c",
    )

    metric_contracts = {
        "fivegs_ep_n3_gtp_indatapktn3upf":
            "Number of incoming GTP data packets on the N3 interface",
        "fivegs_ep_n3_gtp_outdatapktn3upf":
            "Number of outgoing GTP data packets on the N3 interface",
    }
    for name, description in metric_contracts.items():
        require(upf_metrics, f'.name = "{name}"', "src/upf/metrics.c")
        require(
            upf_metrics,
            f'.description = "{description}"',
            "src/upf/metrics.c",
        )

    require_guarded_counter(
        upf_gtp,
        "UPF_METR_GLOB_CTR_GTP_INDATAPKTN3UPF",
    )
    require_guarded_counter(
        upf_gtp,
        "UPF_METR_GLOB_CTR_GTP_OUTDATAPKTN3UPF",
    )

    if "upf_metrics_inst_by_qfi_add(" in upf_gtp:
        raise AssertionError(
            "per-QFI metrics must remain outside the UPF packet hot path"
        )

    print("UPF opt-in N3 Prometheus counter contracts are present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
