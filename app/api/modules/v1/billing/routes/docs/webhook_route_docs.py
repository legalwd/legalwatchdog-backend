# Webhook route documentation for Stripe integration
stripe_webhook_responses = {
    200: {
        "description": "Webhook processed successfully",
        "content": {
            "application/json": {
                "examples": {
                    "processed": {
                        "summary": "Event processed",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Webhook processed",
                            "data": {
                                "processed": True,
                                "action": "invoice.payment_succeeded",
                                "details": {
                                    "invoice_id": "in_123456789",
                                    "billing_account_id": "3f7be7d0-5c7f-4a52-9f87-7fd970000001",
                                },
                            },
                        },
                    },
                    "already_processed": {
                        "summary": "Event previously processed / idempotent",
                        "value": {
                            "status": "SUCCESS",
                            "status_code": 200,
                            "message": "Webhook processed",
                            "data": {
                                "processed": False,
                                "action": "already_processed",
                                "details": {
                                    "event_id": "evt_123456789",
                                },
                            },
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Bad Request - Signature / payload / processing error",
        "content": {
            "application/json": {
                "examples": {
                    "missing_signature": {
                        "summary": "Missing Stripe-Signature header",
                        "value": {
                            "error": "ERROR",
                            "message": "Missing signature header",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "invalid_signature": {
                        "summary": "Invalid webhook signature",
                        "value": {
                            "error": "ERROR",
                            "message": "Invalid webhook signature",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "processing_failed": {
                        "summary": "Event processing failed (Stripe should retry)",
                        "value": {
                            "error": "ERROR",
                            "message": "Processing failed, will retry",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                    "handler_error": {
                        "summary": "Failed to process webhook event",
                        "value": {
                            "error": "ERROR",
                            "message": "Failed to process webhook event",
                            "status_code": 400,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "examples": {
                    "server_error": {
                        "summary": "Unexpected server error",
                        "value": {
                            "error": "INTERNAL_SERVER_ERROR",
                            "message": "Internal server error",
                            "status_code": 500,
                            "errors": {},
                        },
                    },
                }
            }
        },
    },
}

stripe_webhook_custom_errors = ["400", "500"]
stripe_webhook_custom_success = {
    "status_code": 200,
    "description": "Stripe webhook processed successfully.",
}
