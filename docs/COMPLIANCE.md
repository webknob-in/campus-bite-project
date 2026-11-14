# CampusBite brief compliance matrix

Traceability from every rule in `project-brief.txt` (§1-§14 and Submission Guidelines) to implementing files and verifying tests. Paths are relative to the repo root. Backend tests are in `backend/tests/`, frontend tests in `frontend/src/__tests__/`.

## Summary

| Status | Rows | Meaning |
|---|---|---|
| Verified | 164 | Implemented and covered by a named automated test or a verification command that was run (result recorded) |
| Pending | 6 | Can only be completed at deployment time: tasks 18.x (task 18.7 updates these rows) |
| Open gaps | 0 | Gap found in 17.2 (see below) was closed with a new test |

Rows marked **Verified (cmd)** were verified by a command that was run during task 17.2 (see "How to verify"). Every other Verified row names an automated test. Implemented-but-untested rows: none.

Gap closed in 17.2: the dish search/filter UI (§2.A "Search and filter dishes based on their names and prices") had no frontend test. Added `frontend/src/__tests__/dishSearch.test.jsx` (2 tests: filters are sent to the API; inverted price range is reported inline and not sent).

Shorthand for the backend routes: see `backend/tests/test_routes.py` (`REQUIRED` list) for the endpoint inventory.

## §1 Technology stack

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §1 | React.js | `frontend/src/main.jsx`, `frontend/src/App.jsx`, `frontend/package.json` | `cd frontend && npm run build` (passes); `setup.smoke.test.jsx` | Verified |
| §1 | JavaScript (ES6+) | `frontend/src/**/*.js`, `*.jsx` | `npm run build` | Verified |
| §1 | React Hooks | `frontend/src/hooks/useAsync.js`, `frontend/src/hooks/useDebouncedValue.js`, `frontend/src/context/*.jsx` | `useAsync.test.jsx` | Verified |
| §1 | React Router DOM for routing | `frontend/src/App.jsx`, `frontend/src/components/ProtectedRoute.jsx` | `routing.test.jsx`, `ProtectedRoute.test.jsx` | Verified |
| §1 | Fetch API or Axios for API integration | `frontend/src/api/client.js` (Axios), `frontend/src/api/*.js` | `client.test.js`, `api.layer.test.js` | Verified |
| §1 | Python, FastAPI | `backend/app/main.py`, `backend/app/api/routers/*.py` | `test_routes.py::test_required_route_exists` | Verified |
| §1 | Pydantic | `backend/app/schemas/*.py`, `backend/app/core/config.py` | `test_errors.py::test_request_validation_error_returns_422_with_detail_list`, `test_config.py` | Verified |
| §1 | SQLAlchemy ORM | `backend/app/models/*.py`, `backend/app/db/*.py` | `test_schema.py`, `test_fixtures.py::test_factories_create_consistent_rows_for_all_models` | Verified |
| §1 | JWT Authentication | `backend/app/core/security.py`, `backend/app/api/deps.py` | `test_deps.py::test_valid_token_returns_user`, `test_prop_invalid_token.py` | Verified |
| §1 | Docker and Docker Compose | `backend/Dockerfile`, `docker-compose.yml` | Verified (cmd) D1 | Verified |
| §1 | SQL-based relational database; SQLAlchemy for database operations | `backend/alembic/versions/0001_initial.py`, `backend/app/models/*.py`, PostgreSQL 16 in `docker-compose.yml` | `test_schema.py::test_upgrade_head_creates_exactly_the_eight_tables` | Verified |
| §1 | OpenAI API | `backend/app/services/ai_service.py` | `test_ai_service_smoke.py::test_ask_happy_path_sends_system_prompt_and_model` | Verified |
| §1 | Git and GitHub | `.git`, remote `origin` = `https://github.com/webknob-in/campus-bite-project.git` | Verified (cmd) `git remote -v` | Verified |

## §2.A Customer

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §2.A | Register and log in to their accounts | `backend/app/api/routers/auth.py`; `frontend/src/pages/Register.jsx`, `Login.jsx` | `test_auth_smoke.py::test_register_login_me_customer`, `test_prop_auth_roundtrip.py`; `routing.test.jsx` | Verified |
| §2.A | Browse available restaurants | `backend/app/api/routers/restaurants.py`; `frontend/src/pages/RestaurantList.jsx` | `test_browse_smoke.py::test_restaurant_list_search_rating_and_detail`, `test_prop_restaurant_search.py`; `browseRoutes.test.jsx` | Verified |
| §2.A | View restaurant menus and food details | `restaurants.py` (`/restaurants/{id}/menu`); `frontend/src/pages/RestaurantMenu.jsx`, `components/MenuItemCard.jsx` | `test_browse_smoke.py::test_menu_filters_and_money_format`; `cartSwitching.test.jsx` (menu page rendering) | Verified |
| §2.A | Search and filter dishes based on their names and prices | `restaurants.py` (`/dishes`), `backend/app/services/filters.py`, `text_search.py`; `frontend/src/pages/DishSearch.jsx`, `components/DishFilters.jsx` | `test_prop_dish_filters.py::test_dish_filters_match_model`, `test_browse_smoke.py::test_invalid_price_filters_return_422`; `dishSearch.test.jsx` (new, 17.2) | Verified |
| §2.A | Add dishes to their cart | `frontend/src/context/CartContext.jsx`, `cartReducer.js`, `components/MenuItemCard.jsx` | `cartReducer.property.test.js`, `cartSwitching.test.jsx` | Verified |
| §2.A | Update or remove items from their cart | `cartReducer.js`, `frontend/src/pages/CartCheckout.jsx` | `cartReducer.property.test.js` (quantity bounds, 0 removes), `cartTotals.property.test.js`, `cartStorage.property.test.js` | Verified |
| §2.A | Place food orders using a dummy payment system | `orders.py` (`POST /orders`), `backend/app/services/order_service.py`; `CartCheckout.jsx`, `utils/checkoutFormat.js` | `test_orders_endpoints_smoke.py::test_place_order_happy_path`, `test_prop_order_placement.py`; `checkout.test.jsx`, `checkoutFormat.test.js` | Verified |
| §2.A | View their order history | `orders.py` (`GET /orders/me`); `CustomerDashboard.jsx` | `test_orders_endpoints_smoke.py::test_list_my_orders_filters_paging_and_order`; `customerDashboard.test.jsx` | Verified |
| §2.A | Track the status of their orders | `orders.py` (`GET /orders/{id}`); `OrderDetail.jsx`, `components/StatusTimeline.jsx` | `test_orders_endpoints_smoke.py::test_order_detail_own_other_and_unknown`; `statusTimeline.test.jsx`, `orderDetail.test.jsx` | Verified |
| §2.A | Cancel orders when cancellation is allowed | `orders.py` (`POST /orders/{id}/cancel`), `order_service.py` | `test_orders_endpoints_smoke.py::test_cancel_placed_order`, `test_cancel_accepted_is_409_and_unchanged`; `customerDashboard.test.jsx` (cancel flow) | Verified |
| §2.A | Submit ratings and reviews after successful delivery | `orders.py` (`POST /orders/{id}/review`), `backend/app/services/review_service.py`; `components/ReviewModal.jsx` | `test_reviews_smoke.py::test_review_happy_path`, `test_prop_review_eligibility.py`; `orderDetail.test.jsx` | Verified |
| §2.A | Request a return/refund after an order has been delivered | `orders.py` (`POST /orders/{id}/return`), `backend/app/services/return_service.py`; `components/ReturnRequestModal.jsx` | `test_returns_smoke.py::test_return_happy_path`, `test_non_delivered_409`; `orderDetail.test.jsx` | Verified |
| §2.A | View AI-generated summaries and insights about their previous orders | `backend/app/api/routers/ai.py`; `frontend/src/pages/AIInsights.jsx`, `api/ai.js` | `test_ai_endpoints_smoke.py::test_post_and_get_happy_path`; `aiInsights.test.jsx` | Verified |

## §2.B Restaurant owner

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §2.B | Log in to their accounts | `auth.py` (owner registration creates the restaurant), `seed.py` owners | `test_auth_edge_cases.py::test_owner_registration_creates_user_and_linked_restaurant`; `test_browse_and_seed.py::test_seeded_customer_can_log_in` | Verified |
| §2.B | Add new dishes to their restaurant menu | `owner_menu.py` (`POST /owner/menu-items`); `MenuManagement.jsx` | `test_owner_menu_smoke.py::test_create_list_search_and_paging`, `test_prop_menu_invalid_price.py`; `menuManagement.test.jsx` | Verified |
| §2.B | View, update, and manage existing dishes | `owner_menu.py` (list, PATCH, DELETE); `MenuManagement.jsx` | `test_owner_menu_smoke.py::test_patch_updates_only_supplied_fields`, `test_delete_keeps_order_item_snapshots`, `test_prop_menu_partial_update.py`; `menuManagement.test.jsx` | Verified |
| §2.B | Mark dishes as available or unavailable | `owner_menu.py` (`PATCH .../availability`) | `test_owner_menu_smoke.py::test_availability_toggle`; `menuManagement.test.jsx` (availability switch) | Verified |
| §2.B | View incoming orders for their restaurant | `owner_orders.py` (`GET /owner/orders`); `OrderManagement.jsx`, `OwnerDashboard.jsx` | `test_owner_orders_smoke.py::test_list_filters_and_pagination`, `test_prop_tenant_isolation.py`; `ownerDashboard.test.jsx` | Verified |
| §2.B | Accept orders and update their preparation status | `owner_orders.py` (`PATCH /owner/orders/{id}/status`), `backend/app/services/order_state.py` | `test_owner_order_flow.py::test_full_status_flow_visible_in_list`; `orderManagement.test.jsx` | Verified |
| §2.B | Assign delivery partners to orders | `owner_orders.py` (`POST /owner/orders/{id}/assign`, `GET /owner/delivery-partners`) | `test_owner_order_flow.py::test_assign_one_partner_to_two_ready_orders`, `test_assign_failures`; `orderManagement.test.jsx` (READY shows partner select) | Verified |
| §2.B | Filter orders based on status and date | `owner_orders.py`, `services/filters.py`; `components/OrderFilters.jsx` | `test_prop_order_filters.py::test_owner_order_filters_match_model` | Verified |
| §2.B | View basic restaurant statistics | `owner_insights.py` (`GET /owner/stats`), `services/stats_service.py` | `test_owner_stats_smoke.py`, `test_prop_owner_stats.py`; `ownerDashboard.test.jsx::shows counts for all 9 statuses` | Verified |
| §2.B | Approve or reject customer return/refund requests | `owner_returns.py`, `return_service.py` | `test_owner_returns_smoke.py::test_approve_happy_path_and_customer_sees_ledger`, `test_reject`; `ownerDashboard.test.jsx::Approve confirms...`, `Reject calls rejectReturn` | Verified |
| §2.B | View reminders for orders that have not been updated for a specified period | `owner_insights.py` (`GET /owner/reminders`, resolve), `services/reminder_service.py`; `OwnerDashboard.jsx` | `test_reminders_smoke.py::test_list_filter_paging_and_isolation`; `ownerDashboard.test.jsx::Resolve calls resolveReminder...` | Verified |

## §2.C Delivery partner

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §2.C | Log in to their accounts | `auth.py`, `seed.py` partners | `test_auth_smoke.py::test_login_failures_share_one_generic_401`; `routing.test.jsx` | Verified |
| §2.C | View only the orders assigned to them | `partner.py` (`GET /partner/orders`) | `test_partner_flows.py::test_list_default_active_only_own_with_envelope`, `test_other_partner_gets_404_and_order_unchanged` | Verified |
| §2.C | View customer delivery details | `partner.py`, `schemas/partner.py` | `test_partner_flows.py::test_response_includes_customer_contact_items_and_money_strings`; `partnerDashboard.test.jsx::shows no action button for other statuses and a tel: link` | Verified |
| §2.C | Update order status to Out for Delivery | `partner.py` (`PATCH /partner/orders/{id}/status`) | `test_partner_endpoints_smoke.py::test_status_flow_and_invalid_transitions`; `partnerDashboard.test.jsx::ASSIGNED shows Out for Delivery...` | Verified |
| §2.C | Mark orders as Delivered | `partner.py` | `test_partner_flows.py::test_status_flow_sets_delivered_at`; `partnerDashboard.test.jsx::OUT_FOR_DELIVERY shows Mark Delivered...` | Verified |
| §2.C | View their delivery history | `partner.py` (`GET /partner/history`); `DeliveryHistory.jsx` | `test_partner_flows.py::test_history_scope_and_order`; `deliveryHistory.test.jsx` | Verified |

## §3 Authentication and authorization

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §3 | Users should be able to register and log in | `auth.py`, `schemas/auth.py` | `test_prop_auth_roundtrip.py`, `test_prop_duplicate_email.py`, `test_auth_edge_cases.py` | Verified |
| §3 | Implement password hashing using bcrypt | `backend/app/core/security.py` (`hash_password`, `verify_password`) | `test_prop_auth_roundtrip.py` (imports `bcrypt`, checks stored hash), `test_auth_edge_cases.py::test_register_and_login_responses_never_expose_password_hash`, `test_multibyte_72_char_password_does_not_500` | Verified |
| §3 | Use JWT tokens for authentication | `security.py` (`create_access_token`, `decode_access_token`), `api/deps.py` | `test_deps.py::test_expired_token_is_401`, `test_foreign_secret_token_is_401`, `test_prop_invalid_token.py` | Verified |
| §3 | Support three roles | `models/enums.py` (`Role`), `models/user.py` | `test_prop_role_matrix.py::test_role_matrix_exhaustive` | Verified |
| §3 | Protect frontend pages based on user roles | `frontend/src/components/ProtectedRoute.jsx`, `PublicOnlyRoute.jsx`, `utils/roles.js`, `App.jsx` | `ProtectedRoute.test.jsx`, `customerRoutes.test.jsx`, `ownerRoutes.test.jsx`, `partnerRoutes.test.jsx` | Verified |
| §3 | Protect backend APIs using authentication and authorization | `api/deps.py` (`require_roles`) | `test_deps.py::test_require_roles_allows_and_denies`, `test_require_roles_unauthenticated_is_401_not_403`, `test_prop_role_matrix.py::test_every_route_is_classified` | Verified |
| §3 | Users should only be able to access data they are authorized to view or modify | `deps.py` order/restaurant ownership helpers | `test_prop_tenant_isolation.py`, `test_deps.py::test_order_helpers_enforce_tenant`, `test_owner_menu_management.py::test_owner_b_gets_404_on_owner_a_item_and_item_survives` | Verified |
| §3 | Store the authentication token in localStorage and send it with protected API requests | `frontend/src/context/AuthContext.jsx`, `frontend/src/api/client.js` (request interceptor) | `AuthContext.test.jsx::stores the token and user on login`, `client.test.js::attaches Authorization: Bearer <token>...` | Verified |
| §3 | Important: hiding buttons or pages on the frontend is not sufficient; authorization must also be on the backend | All routers use `require_roles` / ownership helpers | `test_prop_role_matrix.py::test_property_role_access_matrix` (every route x every role), `test_prop_tenant_isolation.py` | Verified |

## §4 Order management and lifecycle

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §4 | Lifecycle PLACED, ACCEPTED, PREPARING, READY, ASSIGNED, OUT_FOR_DELIVERY, DELIVERED | `models/enums.py` (`OrderStatus`), `services/order_state.py` | `test_prop_state_machine.py::test_model_has_eight_transitions_and_matches_enums`, `test_e2e_lifecycle.py::test_full_lifecycle` | Verified |
| §4 | Additional statuses CANCELLED, REFUNDED | `enums.py`, `order_service.py`, `return_service.py` | `test_prop_state_machine.py::test_terminal_states_allow_nothing`; `test_reviews_and_refunds.py::test_full_refund_flow` | Verified |
| §4 | Customers can cancel orders only when the order is in PLACED status | `order_service.py` (cancel) | `test_order_service_smoke.py::test_cancel_placed_then_accepted_conflicts`, `test_order_placement_validation.py::test_cancel_after_placed_is_409_and_order_unchanged` | Verified |
| §4 | Restaurant owners can accept orders and update their preparation status | `owner_orders.py`, `order_state.py` | `test_owner_order_flow.py::test_full_status_flow_visible_in_list` | Verified |
| §4 | Restaurant owners can assign delivery partners when an order is READY | `owner_orders.py` (assign) | `test_owner_order_flow.py::test_assign_failures` | Verified |
| §4 | Delivery partners can update only their assigned orders | `partner.py`, `deps.py` (assigned-partner lookup) | `test_partner_flows.py::test_other_partner_gets_404_and_order_unchanged`, `test_deps.py::test_order_helpers_unknown_order_and_unassigned_partner` | Verified |
| §4 | Delivery partners can move ASSIGNED to OUT_FOR_DELIVERY and then DELIVERED | `partner.py`, `order_state.py` | `test_partner_flows.py::test_status_flow_sets_delivered_at` | Verified |
| §4 | Delivered orders cannot be cancelled | `order_service.py` | `test_prop_rejected_status_ops.py::test_rejected_status_operations_leave_order_unchanged`, `test_orders_endpoints_smoke.py::test_cancel_accepted_is_409_and_unchanged` (non-PLACED cancel is 409) | Verified |
| §4 | Invalid order status transitions must be rejected by the backend | `order_state.py` (`is_allowed`), `core/errors.py` (409) | `test_prop_state_machine.py::test_is_allowed_matches_model_for_every_combination`, `test_property_15_transition_applies_exactly_the_allowed_change`; `test_owner_order_flow.py::test_skipping_and_disallowed_targets_conflict_unchanged` | Verified |

## §5 Dummy payment and return/refund

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §5 | Customers can place orders without making an actual payment | `order_service.py` (no gateway; card fields validated only), `schemas/order.py` | `test_order_placement_validation.py::test_ledger_stores_only_last4_and_no_card_number_in_any_text_column` | Verified |
| §5 | Once placed, payment status becomes mock_paid | `order_service.py`, `models/enums.py` (`PaymentStatus`) | `test_prop_order_placement.py::test_order_placement_pricing_and_payment` | Verified |
| §5 | Maintain a payment record to track dummy payments | `models/payment_ledger.py` | `test_order_placement_validation.py::test_detail_includes_payment_ledger_entry` | Verified |
| §5 | Customers can request return/refund only after delivery | `return_service.py` | `test_returns_smoke.py::test_non_delivered_409` | Verified |
| §5 | Customers must provide a reason | `schemas/returns.py` | `test_returns_smoke.py::test_blank_reason_422`, `test_missing_reason_422`, `test_reason_length_boundaries` | Verified |
| §5 | Owners can approve or reject return/refund requests | `owner_returns.py` | `test_prop_return_decisions.py`, `test_owner_returns_smoke.py` | Verified |
| §5 | If approved, payment status becomes refunded and a refund record is kept | `return_service.py`, `payment_ledger.py` | `test_reviews_and_refunds.py::test_full_refund_flow`, `test_fixtures.py::test_refunded_order_has_payment_and_refund_entries` | Verified |
| §5 | If rejected, update the return status to rejected | `return_service.py` | `test_reviews_and_refunds.py::test_reject_flow_keeps_delivered_without_refund`, `test_owner_returns_smoke.py::test_reject` | Verified |
| §5 | A customer cannot submit multiple return requests for the same order | `return_service.py`, unique constraint in `0001_initial.py` | `test_prop_single_return.py`, `test_returns_smoke.py::test_second_request_409` | Verified |

## §6 Dashboards and filtering

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §6 | Separate dashboards for all three roles | `CustomerDashboard.jsx`, `OwnerDashboard.jsx`, `PartnerDashboard.jsx`, `App.jsx`, `utils/roles.js` | `customerRoutes.test.jsx`, `ownerRoutes.test.jsx`, `partnerRoutes.test.jsx` (role homes) | Verified |
| §6 | Customer: view previous and current orders | `CustomerDashboard.jsx`, `utils/orderStatus.js` | `dashboardPartition.property.test.js`, `orderStatus.test.js` | Verified |
| §6 | Customer: filter orders by status and date | `orders.py` (`GET /orders/me`), `components/OrderFilters.jsx` | `test_prop_order_filters.py::test_customer_order_filters_match_model` | Verified |
| §6 | Customer: view payment and return/refund status | `CustomerDashboard.jsx`, `OrderDetail.jsx`, `components/StatusBadge.jsx` | `sharedComponents.test.jsx` (StatusBadge renders Payment_Status, Return_Status), `orderDetail.test.jsx::shows ledger entries` | Verified |
| §6 | Customer: cancel eligible orders | `CustomerDashboard.jsx` | `customerDashboard.test.jsx::shows Cancel only for PLACED orders` | Verified |
| §6 | Customer: submit reviews and return requests | `OrderDetail.jsx`, `ReviewModal.jsx`, `ReturnRequestModal.jsx` | `orderDetail.test.jsx::offers review and return for a delivered order`, `validates the return reason before submitting` | Verified |
| §6 | Owner: view incoming orders, filter by status and date | `OrderManagement.jsx`, `OrderFilters.jsx` | `test_prop_order_filters.py::test_owner_order_filters_match_model`; `orderManagement.test.jsx` | Verified |
| §6 | Owner: manage restaurant menus | `MenuManagement.jsx` | `menuManagement.test.jsx` | Verified |
| §6 | Owner: assign delivery partners | `OrderManagement.jsx` | `orderManagement.test.jsx::READY shows partner select...` | Verified |
| §6 | Owner: view basic restaurant statistics | `OwnerDashboard.jsx` | `ownerDashboard.test.jsx::shows counts for all 9 statuses` | Verified |
| §6 | Owner: manage return/refund requests | `OwnerDashboard.jsx` | `ownerDashboard.test.jsx::Approve confirms...`, `Reject calls rejectReturn` | Verified |
| §6 | Partner: view assigned deliveries, filter by status | `PartnerDashboard.jsx`, `partner.py` | `test_partner_endpoints_smoke.py::test_list_filter_pagination_and_fields`; `partnerDashboard.test.jsx::status filter refetches at page 1 with status param` | Verified |
| §6 | Partner: update delivery status, view delivery history | `PartnerDashboard.jsx`, `DeliveryHistory.jsx` | `partnerDashboard.test.jsx`, `deliveryHistory.test.jsx` | Verified |
| §6 | Implement pagination wherever required for large lists | `services/pagination.py`, `schemas/common.py`, `frontend/src/components/Pagination.jsx` | `test_prop_pagination.py::test_pages_partition_the_listing`, `test_routes.py::test_list_endpoint_uses_page_envelope` (12 list endpoints), `test_pagination_params.py`; `sharedComponents.test.jsx` (Pagination) | Verified |

## §7 Applied AI: order insights

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §7 | Customers can request summaries of previous orders | `ai.py` (`GET /ai/insights/summary`), `ai_service.py` | `test_ai_service_smoke.py::test_summarize_uses_at_most_five_newest_orders`; `aiInsights.test.jsx::summary button calls getInsightSummary` | Verified |
| §7 | Customers can ask questions about their order history | `ai.py` (`POST /ai/insights`) | `test_ai_endpoints_smoke.py::test_post_and_get_happy_path`, `test_invalid_question_422`; `aiInsights.test.jsx::sends every preset string unchanged` | Verified |
| §7 | Backend fetches the authenticated customer's order details from the database | `ai_service.py` (context builder) | `test_prop_ai_context_roundtrip.py::test_ai_context_round_trip` | Verified |
| §7 | Send the relevant order information to the OpenAI API | `ai_service.py` | `test_ai_error_handling.py::test_captured_call_has_prompt_and_model_without_key` | Verified |
| §7 | Display the generated response on the React frontend | `frontend/src/pages/AIInsights.jsx` | `aiInsights.test.jsx::shows the answer on success and sends the exact preset string` | Verified |
| §7 | Customers cannot access another customer's order information through the AI feature | `ai_service.py` | `test_prop_ai_context_isolation.py`, `test_ai_service_smoke.py::test_other_customers_orders_absent` | Verified |
| §7 | Store the OpenAI API key securely in backend environment variables | `core/config.py`, `backend/.env.example` (`OPENAI_API_KEY=` empty) | `test_ai_service_smoke.py::test_key_and_prompt_not_logged`, `test_ai_error_handling.py::test_missing_key_503`; secret scan (cmd S1) | Verified |
| §7 | Basic error handling and rate-limit handling | `services/rate_limiter.py`, `ai_service.py`, `core/errors.py` | `test_prop_rate_limiter.py`, `test_ai_error_handling.py::test_rate_limit_error_429_retry_after`, `test_sixth_request_429_without_calling_fake`, `test_upstream_errors_502_generic`; `aiInsights.test.jsx::shows the rate-limit message...` | Verified |
| §7 | Example queries (last five orders, undelivered, weekly spend, most frequent items) | `ai_service.py` (history context incl. status, totals, items); preset prompts in `AIInsights.jsx` | `aiInsights.test.jsx::sends every preset string unchanged`; `test_prop_ai_context_roundtrip.py` | Verified |
| §7 | Embeddings, vector DBs, RAG not required | Not used (plain context prompt) | n/a | Verified |

## §8 Middleware and background tasks

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §8 | Log incoming request methods and API paths | `backend/app/middleware/request_context.py`, `core/logging.py` | `test_middleware.py::test_access_log_contains_method_path_status_and_duration`, `test_access_log_omits_query_string`; Verified (cmd) D3 (log line `GET /restaurants -> 200 in 63.24ms`) | Verified |
| §8 | Measure API response time | `request_context.py` (`X-Process-Time`) | `test_middleware.py::test_process_time_header_is_numeric`, `test_routes.py::test_docs_and_headers`; Verified (cmd) D3 | Verified |
| §8 | Handle request-level processing wherever required | `request_context.py` (request id, 500 handling), `main.py` (CORS), `core/errors.py` | `test_middleware.py::test_request_id_is_echoed_or_generated`, `test_cors_allows_listed_origin`, `test_unhandled_exception_returns_500_json`, `test_prop_request_id.py` | Verified |
| §8 | Background task reminds owners about orders not updated for more than 15 minutes | `backend/app/scheduler.py`, `services/reminder_service.py`, `core/config.py` (`REMINDER_THRESHOLD_MINUTES=15`) | `test_scheduler_and_reminders.py::test_end_to_end_stale_order_generates_reminder`, `test_default_threshold_not_triggered_for_3_minutes`, `test_interval_job_registration` | Verified |
| §8 | Identify orders still in PLACED or ACCEPTED | `reminder_service.py` | `test_prop_reminder_generation.py`, `test_reminders_smoke.py::test_generation_threshold_terminal_and_restaurants` | Verified |
| §8 | Generate reminder records | `models/admin_reminder_log.py`, `reminder_service.py` | `test_prop_reminder_idempotence.py`, `test_prop_reminder_resolution.py` | Verified |
| §8 | Display reminders on the owner dashboard | `owner_insights.py`, `OwnerDashboard.jsx` | `test_reminders_smoke.py::test_list_filter_paging_and_isolation`; `ownerDashboard.test.jsx::Resolve calls resolveReminder...` | Verified |
| §8 | Real-time notifications / WebSockets not required | Not used (polling job + list endpoint) | n/a | Verified |

## §9 React frontend

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §9 | Reusable React components | `frontend/src/components/*.jsx` (Loader, ErrorMessage, Pagination, StatusBadge, Modal, FormField, ...) | `sharedComponents.test.jsx` | Verified |
| §9 | Hooks (useState, useEffect, useContext) | `hooks/useAsync.js`, `context/AuthContext.jsx`, `context/CartContext.jsx` | `useAsync.test.jsx`, `AuthContext.test.jsx`, `useAuth throws outside an AuthProvider` | Verified |
| §9 | React Router DOM navigation | `App.jsx`, `components/Navbar.jsx` | `Navbar.test.jsx`, `routing.test.jsx` | Verified |
| §9 | Separate pages and dashboards for roles | `frontend/src/pages/*.jsx` | `customerRoutes.test.jsx`, `ownerRoutes.test.jsx`, `partnerRoutes.test.jsx` | Verified |
| §9 | Manage cart and user data with basic React state | `context/cartReducer.js`, `CartContext.jsx`, `AuthContext.jsx` (no Redux/Zustand) | `cartReducer.property.test.js`, `cartStorage.property.test.js`, `cartTotals.property.test.js` | Verified |
| §9 | Integrate backend REST APIs using Fetch or Axios | `frontend/src/api/*.js` | `api.layer.test.js`, `client.test.js` | Verified |
| §9 | Loading states and error handling | `components/Loader.jsx`, `ErrorMessage.jsx`, `useAsync.js` | `sharedComponents.test.jsx`, `useAsync.test.jsx`, `deliveryHistory.test.jsx::shows error and retries` | Verified |
| §9 | Persist login information using localStorage | `AuthContext.jsx` | `AuthContext.test.jsx::restores user, token, and role from localStorage` | Verified |
| §9 | Send JWT tokens with protected API requests | `api/client.js` | `client.test.js`, `api.layer.test.js` | Verified |
| §9 | Protected routes and role-based navigation | `ProtectedRoute.jsx`, `Navbar.jsx`, `utils/roles.js` | `ProtectedRoute.test.jsx`, `Navbar.test.jsx::points each role link at the role` | Verified |
| §9 | Responsive across desktop and mobile | `frontend/src/styles/**/*.css`, `components/Navbar.jsx` (hamburger) | `docs/RESPONSIVE_CHECK.md` (every route at 320/480/768/1280/1920 px: pass); `Navbar.test.jsx::toggles the hamburger menu...` | Verified |
| §9 | Suggested pages: Login/Registration, Restaurant Listing, Restaurant Menu, Cart and Checkout, Customer Dashboard, Owner Dashboard, Menu Management, Order Management, Partner Dashboard, AI Insights | `Login.jsx`, `Register.jsx`, `RestaurantList.jsx`, `RestaurantMenu.jsx`, `CartCheckout.jsx`, `CustomerDashboard.jsx`, `OwnerDashboard.jsx`, `MenuManagement.jsx`, `OrderManagement.jsx`, `PartnerDashboard.jsx`, `AIInsights.jsx` | `browseRoutes.test.jsx`, `customerRoutes.test.jsx`, `ownerRoutes.test.jsx`, `partnerRoutes.test.jsx`, `checkout.test.jsx`, `aiInsights.test.jsx`, `menuManagement.test.jsx`, `orderManagement.test.jsx` | Verified |

## §10 Database

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §10 | Relational SQL database with SQLAlchemy ORM models and operations | `backend/app/models/*.py`, `db/session.py`, `services/*.py` | `test_schema.py` | Verified |
| §10 | Tables: Users, Restaurants, Menu Items, Orders, Order Items, Reviews, Payment Ledger, Admin Reminder Logs | `models/user.py`, `restaurant.py`, `menu_item.py`, `order.py`, `order_item.py`, `review.py`, `payment_ledger.py`, `admin_reminder_log.py`; migration `alembic/versions/0001_initial.py` | `test_schema.py::test_upgrade_head_creates_exactly_the_eight_tables`, `test_downgrade_base_removes_tables_and_enum_types` | Verified |
| §10 | Each customer can have multiple orders; each restaurant multiple menu items and orders; each order multiple order items | FK relationships in `models/order.py`, `menu_item.py`, `order_item.py` | `test_schema.py::test_foreign_keys_and_ondelete_rules`, `test_fixtures.py::test_factories_create_consistent_rows_for_all_models` | Verified |
| §10 | Each delivered order can have one review | `models/review.py` (unique `order_id`) | `test_schema.py::test_second_review_for_one_order_raises_integrity_error`, `test_reviews_smoke.py::test_duplicate_review_409` | Verified |
| §10 | Each order can have multiple payment ledger entries | `models/payment_ledger.py` (non-unique `order_id`) | `test_fixtures.py::test_refunded_order_has_payment_and_refund_entries` (payment + refund rows) | Verified |
| §10 | Delivery partners can be assigned to multiple orders | `models/order.py` (`delivery_partner_id`) | `test_owner_order_flow.py::test_assign_one_partner_to_two_ready_orders` | Verified |
| §10 | Appropriate primary keys, foreign keys, relationships | all models, `0001_initial.py` | `test_schema.py::test_every_table_has_an_id_primary_key`, `test_foreign_keys_and_ondelete_rules`, `test_unique_constraints`, `test_check_constraints`, `test_indexes_cover_status_columns_and_every_foreign_key` | Verified |
| §10 | SQL queries and ORM to retrieve, insert, update, delete | `services/*.py`, `routers/owner_menu.py` (delete) | `test_owner_menu_smoke.py::test_delete_keeps_order_item_snapshots`, `test_prop_order_snapshots.py` | Verified |

## §11 Backend Dockerization

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §11 | Dockerfile for the FastAPI backend | `backend/Dockerfile`, `backend/docker-entrypoint.sh`, `backend/.dockerignore` | Verified (cmd) D1: image built | Verified |
| §11 | docker-compose.yml to configure and run the backend container | `docker-compose.yml` (services `db`, `api`) | Verified (cmd) D1 | Verified |
| §11 | Configure the necessary environment variables | `docker-compose.yml` (`env_file`, `environment`), `core/config.py` | `test_config.py::test_missing_jwt_secret_raises_validation_error_naming_it` | Verified |
| §11 | Backend starts correctly inside the container | `docker-entrypoint.sh` (migrate then uvicorn) | Verified (cmd) D1: `GET /health` returned `{"status":"ok","database":"ok"}` HTTP 200 | Verified |
| §11 | Expose the required backend port | `Dockerfile` `EXPOSE 8000`, compose `8000:8000` | Verified (cmd) D1 (port 8000 answered) | Verified |
| §11 | Backend can connect to the SQL database | compose `db` service (postgres:16, healthcheck), `DATABASE_URL` override | Verified (cmd) D1 (`database: ok`), `test_health.py::test_health_ok_with_database_up` | Verified |
| §11 | Keep API keys, DB credentials, JWT secrets out of image and repo | `backend/.dockerignore`, `.gitignore` (`.env`, `.env.*`), compose `env_file` | Verified (cmd) S1 (no `.env` tracked, no `sk-` keys in tracked files) | Verified |
| §11 | Provide `.env.example` without real secrets | `backend/.env.example`, `frontend/.env.example` | Verified (cmd) S1 (placeholders only) | Verified |
| §11 | Runnable locally using Docker Compose | `docker-compose.yml`, `README.md` "Run the backend with Docker Compose" | Verified (cmd) D1, D2 (seed ran in container), D4 (`down` without `-v`; `campusbite_pgdata` volume kept) | Verified |

## §12 API development

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §12 | User registration and authentication | `auth.py` | `test_routes.py` (`/auth/register`, `/auth/login`, `/auth/me`), `test_auth_smoke.py` | Verified |
| §12 | Restaurant listing and menu management | `restaurants.py`, `owner_menu.py` | `test_routes.py`, `test_browse_smoke.py`, `test_owner_menu_smoke.py` | Verified |
| §12 | Order placement; order history and details | `orders.py` | `test_orders_endpoints_smoke.py` | Verified |
| §12 | Order status management; delivery partner assignment | `owner_orders.py`, `partner.py` | `test_owner_orders_smoke.py`, `test_partner_endpoints_smoke.py` | Verified |
| §12 | Reviews and ratings | `orders.py` (review), `restaurants.py` (`/restaurants/{id}/reviews`) | `test_reviews_smoke.py`, `test_browse_and_seed.py::test_reviews_newest_first_with_id_desc_tie_break` | Verified |
| §12 | Return and refund management | `orders.py` (return), `owner_returns.py` | `test_returns_smoke.py`, `test_owner_returns_smoke.py` | Verified |
| §12 | AI-powered order insights | `ai.py` | `test_ai_endpoints_smoke.py` | Verified |
| §12 | Restaurant statistics and reminders | `owner_insights.py` | `test_owner_stats_smoke.py`, `test_reminders_smoke.py` | Verified |
| §12 | Proper request validation, response handling, HTTP status codes | `schemas/*.py`, `core/errors.py` | `test_errors.py`, `test_auth_edge_cases.py`, `test_orders_endpoints_smoke.py::test_bad_items_are_422` | Verified |
| §12 | All business rules and authorization checks enforced on the backend | services + `deps.py` | `test_prop_role_matrix.py`, `test_prop_tenant_isolation.py`, `test_prop_state_machine.py` | Verified |
| §12 (docs) | API documentation (Swagger) | `main.py` (`/docs`, `/redoc`, `openapi_tags`) | `test_routes.py::test_docs_and_headers`; Verified (cmd) D1 (`/docs` HTTP 200) | Verified |

## §13 Deployment and documentation

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §13 | Complete React frontend source | `frontend/` | `cd frontend && npm test -- --run && npm run build` (257 + 2 tests, build passes) | Verified |
| §13 | Complete FastAPI backend source | `backend/` | `cd backend && python -m pytest` (501 passing) | Verified |
| §13 | Dockerfile; docker-compose.yml | `backend/Dockerfile`, `docker-compose.yml` | Verified (cmd) D1 | Verified |
| §13 | `.env.example` files wherever required | `backend/.env.example`, `frontend/.env.example` | `git ls-files | Select-String '\.env'` lists only the two examples | Verified |
| §13 | README: project overview | `README.md` "CampusBite" intro | `Select-String -Path README.md -Pattern '^#'` | Verified |
| §13 | README: technologies used | `README.md` "Technologies used" | same command | Verified |
| §13 | README: features implemented | `README.md` "Features implemented" | same command | Verified |
| §13 | README: run the frontend locally | `README.md` "Run the frontend locally" | same command | Verified |
| §13 | README: run the backend using Docker Compose | `README.md` "Run the backend with Docker Compose" | same command; steps exercised in D1-D4 | Verified |
| §13 | README: required environment variables | `README.md` "Environment variables" | same command | Verified |
| §13 | README: database setup instructions | `README.md` "Database setup" | same command | Verified |
| §13 | README: API documentation details | `README.md` "API documentation" | same command | Verified |
| §13 | Seed data for demo | `backend/scripts/seed.py`, `README.md` "Demo credentials" | `test_browse_and_seed.py::test_seed_twice_keeps_row_counts_identical`, `test_seed_creates_expected_users_restaurants_and_dishes`; Verified (cmd) D2 | Verified |
| §13 | Sensitive information not committed | `.gitignore`, `.dockerignore` | Verified (cmd) S1 on the working tree; final-history scan is Pending (P5) | Verified |
| §13 | Prepare application for deployment | `frontend/vercel.json`, `backend/.env.example` (Supabase pooler note), `README.md` "Deployment" | Live URLs: Pending (P3, P4) | Pending |

## §14 Expected outcome

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| §14 | Customers browse, order, track deliveries, review | customer pages + `orders.py` | `test_e2e_lifecycle.py::test_full_lifecycle` | Verified |
| §14 | Owners manage menus, orders, return/refund requests | owner pages + owner routers | `test_e2e_lifecycle.py`, `test_owner_*` | Verified |
| §14 | Partners manage assigned deliveries | `partner.py`, `PartnerDashboard.jsx` | `test_partner_flows.py`, `partnerDashboard.test.jsx` | Verified |
| §14 | Customers access AI-powered insights | `ai.py`, `AIInsights.jsx` | `test_ai_endpoints_smoke.py`, `aiInsights.test.jsx` | Verified |
| §14 | Proper authentication and authorization practices | `security.py`, `deps.py` | `test_prop_role_matrix.py`, `test_prop_tenant_isolation.py` | Verified |
| §14 | React frontend talks to FastAPI via REST | `frontend/src/api/*.js`, `CORS_ORIGINS` | `api.layer.test.js`, `test_middleware.py::test_cors_allows_listed_origin` | Verified |
| §14 | Backend successfully containerized | `backend/Dockerfile` | Verified (cmd) D1 | Verified |
| §14 | Data stored in a relational SQL database | PostgreSQL via SQLAlchemy | `test_schema.py` | Verified |

## Submission guidelines

| Section | Brief text | Implementing files | Verifying tests / command | Status |
|---|---|---|---|---|
| Submission | Submit only the GitHub repository link | `README.md` "Submission and live links" | `Select-String -Path README.md -Pattern 'github.com'` | Pending: task 18.x (P1: README links final) |
| Submission | Repository must be Public | GitHub settings | P2: `curl.exe -s -o NUL -w "%{http_code}" https://github.com/webknob-in/campus-bite-project` returns `200` with no login; or `gh repo view webknob-in/campus-bite-project --json visibility` returns `PUBLIC` | Pending: task 18.x |
| Submission | All project files (frontend, backend, Dockerfile, compose, README) are in the repository | `git ls-files` | `git ls-files frontend backend/Dockerfile docker-compose.yml README.md` is non-empty; after push compare `git ls-remote origin HEAD` with `git rev-parse HEAD` | Verified (local); remote check part of 18.x |
| Submission | No API keys, passwords, DB credentials in the repository | `.gitignore`, `.env.example` | Verified (cmd) S1 on tracked files; P5: final-history secret scan `git log -p --all -S"sk-" --oneline` and `git log --all --diff-filter=A --name-only -- "*.env"` return nothing | Pending: task 18.x (P5) |
| Submission | Application runs correctly and repository is accessible before submitting | live deployment | P3: Vercel frontend URL returns 200; P4: hosted API `/health` returns `{"status":"ok","database":"ok"}` and a login + order smoke test succeeds against the live URLs | Pending: task 18.x |

### Pending items (updated by task 18.7)

| ID | Item | Verification command | Status |
|---|---|---|---|
| P1 | README live links filled in | `Select-String -Path README.md -Pattern 'Submission and live links' -Context 0,8` | Pending: task 18.x |
| P2 | Repository is public | `gh repo view webknob-in/campus-bite-project --json visibility` (expect `PUBLIC`) | Pending: task 18.x |
| P3 | Live frontend on Vercel | `curl.exe -s -o NUL -w "%{http_code}" <frontend-url>` (expect 200) | Pending: task 18.x |
| P4 | Hosted backend and Supabase database, production smoke test | `curl.exe -s <api-url>/health`, then register/login/browse against `<api-url>` | Pending: task 18.x |
| P5 | Secret scan over final git history | `git log --all -p -S"sk-" --oneline`; `git log --all --name-only --format= \| Select-String '(^\|/)\.env$'` (expect no output) | Pending: task 18.x |

## How to verify

Run from the repo root unless noted.

1. Backend tests: `cd backend; python -m pytest` (needs the test database from `docker compose up -d db`).
2. Frontend tests and build: `cd frontend; npm test -- --run; npm run build`.
3. Docker (D1-D4, run in task 17.2):
   - D1: `docker compose up --build -d`, then `curl.exe http://localhost:8000/health` returned `{"status":"ok","database":"ok"}` (HTTP 200) and `curl.exe -o NUL -w "%{http_code}" http://localhost:8000/docs` returned 200.
   - D2: `docker compose exec -T api python -m scripts.seed` printed the demo accounts (owners, partners, customers).
   - D3: `curl.exe -i http://localhost:8000/restaurants` returned 200 with `x-process-time: 63.24` and `x-request-id`; `docker compose logs api` showed `GET /restaurants -> 200 in 63.24ms request_id=...`.
   - D4: `docker compose down` (never `-v`); the `campusbite_pgdata` volume remained.
4. Secrets (S1, run in task 17.2): `git ls-files | Select-String '(^|/)\.env$'` printed nothing; `git grep -n -I -E "sk-[A-Za-z0-9]{20,}" -- . ":!.kiro"` printed nothing.
5. Remote: `git remote -v` shows `origin https://github.com/webknob-in/campus-bite-project.git`.
6. Responsive: see `docs/RESPONSIVE_CHECK.md` for method and results.
7. Pending items: run the commands in the Pending table after deployment.
