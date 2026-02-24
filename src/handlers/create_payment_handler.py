"""
Handler: create payment transaction
SPDX - License - Identifier: LGPL - 3.0 - or -later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""
import requests
import config
from handlers.handler import Handler
from order_saga_state import OrderSagaState

class CreatePaymentHandler(Handler):
    """ Handle the creation of a payment transaction for a given order. Trigger rollback of previous steps in case of failure. """

    def __init__(self, order_id, order_data):
        """ Constructor method """
        self.order_id = order_id
        self.order_data = order_data
        self.total_amount = 0
        super().__init__()

    def run(self):
        """Call payment microservice to generate payment transaction"""
        try:
            response = requests.get(f'{config.API_GATEWAY_URL}/store-manager-api/orders/{self.order_id}')
            if not response.ok:
                self.logger.error("Erreur:", response.status_code, response.text)
                return self.rollback()
            response_data = response.json()
            self.total_amount = response_data.get('total_amount') if response_data else 0
            user_id = response_data.get('user_id') if response_data else ""
            response = requests.post(f'{config.API_GATEWAY_URL}/payments-api/payments',
                json= {
                    "total_amount":self.total_amount,
                    "user_id": user_id,
                    "order_id": self.order_id
                },
                headers={'Content-Type': 'application/json'}
            )

            if response.ok:
                self.logger.debug("Transition d'état: CreatePayment -> PAYMENT_CREATED")
                return OrderSagaState.PAYMENT_CREATED
            else:
                self.logger.error("Erreur:", response.status_code, response.text)
                return self.rollback()

        except Exception:
            return self.rollback()
        
    def rollback(self):
        """ Call StoreManager to restore stock quantities if payment transaction creation fails """
        try:
            response = requests.put(f'{config.API_GATEWAY_URL}/store-manager-api/stocks',
                json= {
                   "items": self.order_data,
                   "operation": "+"
                },
                headers={'Content-Type': 'application/json'}
            )
            if response.ok:
                self.logger.debug("Transition d'état: CreatePaymentFailure -> STOCK_INCREASED")
                return OrderSagaState.STOCK_INCREASED
            
        except Exception as e:
            self.logger.error("CreatePaymentHandler a échoué : " + str(e))
            return OrderSagaState.END
        
        self.logger.error("CreatePaymentHandler a échoué")
        return OrderSagaState.END