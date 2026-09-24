from datetime import (
    datetime,
    timedelta,
    timezone
)

from sqlalchemy.orm import joinedload

from app.extensions import db

from app.models.inventory import (
    Inventory
)

from app.models.inventoryreservation import (
    InventoryReservation,
    InventoryReservationStatus
)


class InventoryService:

    RESERVATION_TTL_MINUTES = 15

    @staticmethod
    def reserve_inventory_for_order(
        *,
        order,
        cart_items
    ):

        existing_reservations = (
            InventoryReservation.query.filter_by(
                order_id=order.id
            ).first()
        )

        if existing_reservations:
            return

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(
                minutes=(
                    InventoryService
                    .RESERVATION_TTL_MINUTES
                )
            )
        )

        for cart_item in cart_items:

            inventory = (
                Inventory.query
                .join(
                    Inventory.branch_variant
                )
                .filter(
                    Inventory.branch_variant_id
                    == cart_item.branch_variant_id
                )
                .with_for_update()
                .first()
            )

            if not inventory:

                raise ValueError(
                    "Inventory record missing"
                )

            available_quantity = (
                inventory.quantity
                - inventory.reserved_quantity
            )

            if available_quantity < (
                cart_item.quantity
            ):
                raise ValueError(
                    (
                        f"Insufficient inventory "
                        f"for variant "
                        f"{cart_item.branch_variant_id}"
                    )
                )

            inventory.reserved_quantity += (
                cart_item.quantity
            )

            reservation = (
                InventoryReservation(
                    order_id=order.id,
                    inventory_id=inventory.id,
                    quantity=cart_item.quantity,
                    expires_at=expires_at
                )
            )

            db.session.add(reservation)

    @staticmethod
    def commit_order_reservations(order_id):

        reservations = (
            InventoryReservation.query
            .options(
                joinedload(
                    InventoryReservation.inventory
                )
            )
            .filter_by(
                order_id=order_id,
                status=(
                    InventoryReservationStatus
                    .RESERVED
                )
            )
            .with_for_update()
            .all()
        )

        now = datetime.now(timezone.utc)

        for reservation in reservations:

            inventory = reservation.inventory

            if (
                reservation.status
                != InventoryReservationStatus.RESERVED
            ):
                continue

            if (
                inventory.reserved_quantity
                < reservation.quantity
            ):
                raise ValueError(
                    "Inventory corruption detected"
                )

            if (
                inventory.quantity
                < reservation.quantity
            ):
                raise ValueError(
                    "Inventory quantity invalid"
                )

            inventory.quantity -= (
                reservation.quantity
            )

            inventory.reserved_quantity -= (
                reservation.quantity
            )

            reservation.status = (
                InventoryReservationStatus.COMMITTED
            )

            reservation.committed_at = now

    @staticmethod
    def release_order_reservations(order_id):

        reservations = (
            InventoryReservation.query
            .options(
                joinedload(
                    InventoryReservation.inventory
                )
            )
            .filter_by(
                order_id=order_id,
                status=(
                    InventoryReservationStatus
                    .RESERVED
                )
            )
            .with_for_update()
            .all()
        )

        now = datetime.now(timezone.utc)

        for reservation in reservations:

            inventory = reservation.inventory

            inventory.reserved_quantity = max(
                inventory.reserved_quantity
                - reservation.quantity,
                0
            )

            reservation.status = (
                InventoryReservationStatus.RELEASED
            )

            reservation.released_at = now

    @staticmethod
    def expire_stale_reservations():

        now = datetime.now(timezone.utc)

        reservations = (
            InventoryReservation.query
            .options(
                joinedload(
                    InventoryReservation.inventory
                )
            )
            .filter(
                InventoryReservation.status
                == InventoryReservationStatus.RESERVED,
                InventoryReservation.expires_at
                < now
            )
            .with_for_update()
            .all()
        )

        for reservation in reservations:

            inventory = reservation.inventory

            inventory.reserved_quantity = max(
                inventory.reserved_quantity
                - reservation.quantity,
                0
            )

            reservation.status = (
                InventoryReservationStatus.EXPIRED
            )

            reservation.expired_at = now