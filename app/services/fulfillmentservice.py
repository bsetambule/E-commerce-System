from app.services.inventoryservice import InventoryService
from app.services.deliveryservice import DeliveryService
from app.services.otpservice import OtpService
from app.models.deliveryotp import DeliveryOtpType
from app.services.cartservice import CartService

class FulfillmentService:

    @staticmethod
    def process_paid_order(order):

        InventoryService.commit_order_reservations(
            order.id
        )

        delivery = None

        if order.is_delivery:

            delivery = (
                DeliveryService
                .create_delivery_for_order(
                    order
                )
            )

        pickup_otp = (
            OtpService.create_order_otp(
                order=order,
                otp_type=(
                    DeliveryOtpType.PICKUP
                )
            )
        )

        delivery_otp = None

        if delivery:

            delivery_otp = (
                OtpService.create_order_otp(
                    order=order,
                    delivery=delivery,
                    otp_type=(
                        DeliveryOtpType.DELIVERY
                    )
                )
            )

        CartService.clear_user_cart(
            order.user_id
        )

        return {
            "delivery": delivery,
            "pickup_otp": pickup_otp,
            "delivery_otp": delivery_otp
        }