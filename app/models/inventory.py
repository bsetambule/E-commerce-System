from sqlalchemy import CheckConstraint

from app.extensions import db


class Inventory(db.Model):
    __tablename__ = "inventory"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
        autoincrement=True
    )

    branch_variant_id = db.Column(
        db.BigInteger,
        db.ForeignKey("branch_product_variants.id"),
        nullable=False,
        unique=True,
        index=True
    )

    quantity = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    reserved_quantity = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now()
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now(),
        onupdate=db.func.now()
    )

    branch_variant = db.relationship(
        "BranchProductVariant",
        back_populates="inventory"
    )

    reservations = db.relationship(
        "InventoryReservation",
        back_populates="inventory"
    )

    __table_args__ = (

        CheckConstraint(
            "quantity >= 0",
            name="ck_inventory_quantity_non_negative"
        ),

        CheckConstraint(
            "reserved_quantity >= 0",
            name="ck_inventory_reserved_non_negative"
        ),

        CheckConstraint(
            "reserved_quantity <= quantity",
            name="ck_inventory_reserved_lte_quantity"
        ),
    )

    @property
    def available_quantity(self):

        return (
            self.quantity
            - self.reserved_quantity
        )