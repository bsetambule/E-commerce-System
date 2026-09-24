from app.extensions import db

from app.models.delivery import (
    Delivery,
    DeliveryStatus
)

from app.services.deliveryzoneservice import (
    DeliveryZoneService
)


class DeliveryService:

    @staticmethod
    def create_delivery_for_order(
        order
    ):

        if not order.is_delivery:
            return None

        existing_delivery = (
            Delivery.query.filter_by(
                order_id=order.id
            ).first()
        )

        if existing_delivery:
            return existing_delivery

        address = order.address

        zone = (
            DeliveryZoneService.get_branch_zone(
                order.branch_id,
                address.area
            )
        )

        if not zone:
            raise ValueError(
                "Delivery zone not configured"
            )

        delivery = Delivery(
            order_id=order.id,
            branch_id=order.branch_id,
            status=DeliveryStatus.UNASSIGNED,
            delivery_zone_id=(
                zone.delivery_zone_id
            ),
            delivery_zone_name=(
                zone.delivery_zone.name
            ),
            delivery_fee_applied=(
                order.delivery_fee
            ),
            delivery_address_snapshot={
                "first_name":
                    address.first_name,

                "last_name":
                    address.last_name,

                "phone":
                    address.phone,

                "city":
                    address.city,

                "region":
                    address.region,

                "area":
                    address.area,

                "plot_number":
                    address.plot_number,

                "delivery_notes":
                    address.delivery_notes
            }
        )

        db.session.add(delivery)

        db.session.flush()

        return delivery