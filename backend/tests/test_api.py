"""End-to-end API tests against the real seed data."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def center_id(client: TestClient) -> str:
    return client.get("/api/centers").json()[0]["id"]


class TestHealth:
    def test_reports_loaded_data(self, client: TestClient) -> None:
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["centers_loaded"] > 0
        assert body["last_refresh"] is not None


class TestCenters:
    def test_lists_centers(self, client: TestClient) -> None:
        centers = client.get("/api/centers").json()
        assert len(centers) >= 10
        first = centers[0]
        assert first["name"]
        assert first["status_label"]
        assert first["district_label"]

    def test_sorted_by_volume(self, client: TestClient) -> None:
        volumes = [c["daily_contacts"] for c in client.get("/api/centers").json()]
        assert volumes == sorted(volumes, reverse=True)

    def test_search_matches_name(self, client: TestClient) -> None:
        results = client.get("/api/centers", params={"search": "רפואה"}).json()
        assert results
        assert all("רפואה" in c["name"] for c in results)

    def test_search_matches_id(self, client: TestClient) -> None:
        results = client.get("/api/centers", params={"search": "SC-10"}).json()
        assert results

    def test_filters_combine(self, client: TestClient) -> None:
        results = client.get(
            "/api/centers", params={"center_type": "medical", "district": "north"}
        ).json()
        for center in results:
            assert center["center_type"] == "medical"
            assert center["district"] == "north"

    def test_unknown_filter_value_is_rejected(self, client: TestClient) -> None:
        assert client.get("/api/centers", params={"district": "atlantis"}).status_code == 422

    def test_filter_options_carry_labels(self, client: TestClient) -> None:
        options = client.get("/api/centers/filters").json()
        assert {"center_type", "district", "status", "size"} <= options.keys()
        assert all(entry["label"] for entry in options["district"])

    def test_missing_center_is_404(self, client: TestClient) -> None:
        assert client.get("/api/centers/SC-NOPE").status_code == 404

    def test_status_spread_is_meaningful(self, client: TestClient) -> None:
        """A fleet where everything is fine has nothing to decide about."""
        statuses = {c["status"] for c in client.get("/api/centers").json()}
        assert len(statuses) >= 2


class TestSnapshot:
    def test_carries_baseline_and_levers(self, client: TestClient, center_id: str) -> None:
        snap = client.get(f"/api/centers/{center_id}/snapshot").json()
        assert snap["id"].startswith("snap_")
        assert snap["baseline"]["daily_contacts"] > 0
        assert snap["lever_defaults"]["digital_adoption"] >= 0
        assert snap["trend"]

    def test_id_is_stable_across_reads(self, client: TestClient, center_id: str) -> None:
        """Content-derived, so an unchanged refresh does not orphan open scenarios."""
        first = client.get(f"/api/centers/{center_id}/snapshot").json()["id"]
        second = client.get(f"/api/centers/{center_id}/snapshot").json()["id"]
        assert first == second

    def test_dynamic_bounds_bracket_the_default(self, client: TestClient, center_id: str) -> None:
        snap = client.get(f"/api/centers/{center_id}/snapshot").json()
        bounds = snap["lever_bounds"]["workforce_capacity"]
        default = snap["lever_defaults"]["workforce_capacity"]
        assert bounds["min"] <= default <= bounds["max"]


class TestMetadata:
    def test_levers_expose_bounds(self, client: TestClient) -> None:
        levers = client.get("/api/levers").json()
        assert len(levers) >= 12
        for lever in levers:
            assert lever["min"] < lever["max"]
            assert lever["label"]
            assert lever["tooltip"]

    def test_tab_filter(self, client: TestClient) -> None:
        digital = client.get("/api/levers", params={"tab": "digital_channels"}).json()
        assert all("digital_channels" in lever["tabs"] for lever in digital)

    def test_metadata_bundle(self, client: TestClient) -> None:
        body = client.get("/api/metadata").json()
        assert len(body["tabs"]) == 2
        assert body["lever_groups"]
        assert body["kpis"]


class TestSimulate:
    def test_empty_scenario_is_a_no_op(self, client: TestClient, center_id: str) -> None:
        result = client.post(
            "/api/simulate", json={"center_id": center_id, "tab": "phone_center", "levers": {}}
        ).json()
        assert all(k["difference"] == 0 for k in result["kpis"])

    def test_causal_chain(self, client: TestClient, center_id: str) -> None:
        snap = client.get(f"/api/centers/{center_id}/snapshot").json()
        current = snap["lever_defaults"]["digital_adoption"]
        result = client.post(
            "/api/simulate",
            json={
                "center_id": center_id,
                "tab": "phone_center",
                "levers": {"digital_adoption": min(current + 20, 100)},
                "snapshot_id": snap["id"],
            },
        ).json()
        kpis = {k["id"]: k for k in result["kpis"]}
        assert kpis["incoming_calls"]["difference"] < 0
        assert kpis["sla"]["difference"] >= 0
        assert result["recommendations"]
        assert result["waterfall"]

    def test_out_of_range_values_are_clamped_not_rejected(
        self, client: TestClient, center_id: str
    ) -> None:
        result = client.post(
            "/api/simulate",
            json={
                "center_id": center_id,
                "tab": "phone_center",
                "levers": {"digital_adoption": 5000},
            },
        ).json()
        assert result["levers"]["digital_adoption"] == 100

    def test_unknown_lever_is_rejected(self, client: TestClient, center_id: str) -> None:
        response = client.post(
            "/api/simulate",
            json={"center_id": center_id, "tab": "phone_center", "levers": {"teleportation": 5}},
        )
        assert response.status_code == 422

    def test_extra_fields_are_rejected(self, client: TestClient, center_id: str) -> None:
        response = client.post(
            "/api/simulate",
            json={"center_id": center_id, "tab": "phone_center", "levers": {}, "sneaky": 1},
        )
        assert response.status_code == 422

    def test_stale_snapshot_still_computes(self, client: TestClient, center_id: str) -> None:
        """A moved baseline must never discard the user's scenario."""
        result = client.post(
            "/api/simulate",
            json={
                "center_id": center_id,
                "tab": "phone_center",
                "levers": {"digital_adoption": 55},
                "snapshot_id": "snap_from_an_hour_ago",
            },
        ).json()
        assert result["snapshot_changed"] is True
        assert result["kpis"]

    def test_missing_center_is_404(self, client: TestClient) -> None:
        response = client.post(
            "/api/simulate", json={"center_id": "SC-NOPE", "tab": "phone_center", "levers": {}}
        )
        assert response.status_code == 404


class TestScenarios:
    def test_lifecycle(self, client: TestClient, center_id: str) -> None:
        created = client.post(
            "/api/scenarios",
            json={
                "center_id": center_id,
                "name": "תרחיש בדיקה",
                "tab": "phone_center",
                "levers": {"digital_adoption": 70},
            },
        )
        assert created.status_code == 201
        scenario_id = created.json()["id"]

        listed = client.get("/api/scenarios", params={"center_id": center_id}).json()
        assert any(s["id"] == scenario_id for s in listed)

        renamed = client.patch(f"/api/scenarios/{scenario_id}", json={"name": "שם מעודכן"})
        assert renamed.json()["name"] == "שם מעודכן"

        assert client.delete(f"/api/scenarios/{scenario_id}").status_code == 204
        assert client.delete(f"/api/scenarios/{scenario_id}").status_code == 404

    def test_rejects_unknown_center(self, client: TestClient) -> None:
        response = client.post(
            "/api/scenarios",
            json={
                "center_id": "SC-NOPE",
                "name": "x",
                "tab": "phone_center",
                "levers": {},
            },
        )
        assert response.status_code == 404

    def test_rejects_blank_name(self, client: TestClient, center_id: str) -> None:
        response = client.post(
            "/api/scenarios",
            json={"center_id": center_id, "name": "", "tab": "phone_center", "levers": {}},
        )
        assert response.status_code == 422

    def test_compare_picks_winners(self, client: TestClient, center_id: str) -> None:
        ids = []
        for name, adoption in (("תרחיש א", 55), ("תרחיש ב", 80)):
            ids.append(
                client.post(
                    "/api/scenarios",
                    json={
                        "center_id": center_id,
                        "name": name,
                        "tab": "phone_center",
                        "levers": {"digital_adoption": adoption},
                    },
                ).json()["id"]
            )

        result = client.post(
            "/api/scenarios/compare", json={"center_id": center_id, "scenario_ids": ids}
        ).json()

        assert len(result["columns"]) == 2
        # The more aggressive deflection must win on volume.
        assert result["winners"]["incoming_calls"] == ids[1]
        # All columns share one snapshot, so the comparison is apples to apples.
        assert result["snapshot_id"]

        # Metrics with a healthy band rather than a direction get no winner —
        # otherwise the table crowns a scenario for being idle, contradicting
        # its own footnote.
        assert "occupancy" not in result["winners"]
        assert "utilization" not in result["winners"]

        for scenario_id in ids:
            client.delete(f"/api/scenarios/{scenario_id}")

    def test_hebrew_names_survive_a_round_trip(self, client: TestClient, center_id: str) -> None:
        """Every visible string in this application is Hebrew."""
        name = "תרחיש עברית · בדיקה"
        created = client.post(
            "/api/scenarios",
            json={
                "center_id": center_id,
                "name": name,
                "tab": "phone_center",
                "levers": {"digital_adoption": 60},
            },
        ).json()

        assert created["name"] == name
        reloaded = next(
            s
            for s in client.get("/api/scenarios", params={"center_id": center_id}).json()
            if s["id"] == created["id"]
        )
        assert reloaded["name"] == name

        client.delete(f"/api/scenarios/{created['id']}")

    def test_compare_rejects_empty_selection(self, client: TestClient, center_id: str) -> None:
        response = client.post(
            "/api/scenarios/compare", json={"center_id": center_id, "scenario_ids": []}
        )
        assert response.status_code == 422


class TestRefresh:
    def test_manual_refresh_keeps_serving(self, client: TestClient, center_id: str) -> None:
        before = client.get(f"/api/centers/{center_id}/snapshot").json()["id"]
        body = client.post("/api/refresh").json()
        assert body["ok"] is True
        after = client.get(f"/api/centers/{center_id}/snapshot").json()["id"]
        # Same source data means the same content hash, so open scenarios are
        # not told they are stale for no reason.
        assert before == after
