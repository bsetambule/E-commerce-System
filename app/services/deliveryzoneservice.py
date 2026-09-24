from decimal import Decimal

from app.models.deliveryzone import DeliveryZone
from app.models.branchdeliveryzone import BranchDeliveryZone


class DeliveryZoneService:

    @staticmethod
    def get_branch_zone(branch_id, area):

        area = (area or "").strip().lower()

        configs = (
            BranchDeliveryZone.query
            .filter_by(
                branch_id=branch_id,
                is_active=True
            )
            .all()
        )

        for config in configs:

            zone = config.delivery_zone

            if not zone:
                continue

            covered = [
                str(x).strip().lower()
                for x in (zone.covered_areas or [])
            ]

            if area in covered:
                return config

        return None

    @staticmethod
    def calculate_fee(
        branch_id,
        area,
        delivery_type
    ):

        config = (
            DeliveryZoneService.get_branch_zone(
                branch_id,
                area
            )
        )

        if not config:
            raise ValueError(
                "Delivery unavailable for selected area"
            )

        fee = Decimal(
            str(config.delivery_fee)
        )

        if delivery_type == "express":
            fee += Decimal("5.00")

        return fee