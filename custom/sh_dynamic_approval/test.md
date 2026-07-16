# Dynamic Approval Module - QA Test Cases

The following are the end-to-end test cases that have been explicitly performed and validated for the Dynamic Approval module.

### Test Case 1: Approval Level Configuration
* **Action:** Create a new Approval Type and configure two Approval Levels under the notebook tab:
  * Level 1: Dynamic Code (Python) -> `record.employee_id.parent_id.user_id` (User C).
  * Level 2: Access Group -> Finance Team (User D & E).
* **Expected Result:** The configuration saves successfully, and the `python_code` field is accessible via a popup form.
* **Status:** **PASS** (Resolved UI inline editing restriction).

### Test Case 2: Approval Request Generation
* **Action:** Log in as User F (Requester) and create/save a Sales Order that matches the Approval Type domain.
* **Expected Result:** The system automatically intercepts the action, creates a Dynamic Approval Request, and assigns User C (Level 1) and Users D/E (Level 2) as pending approvers.
* **Status:** **PASS**

### Test Case 3: Sequential Email Notifications
* **Action:** Observe the outgoing emails generated immediately after User F saves the Sales Order.
* **Expected Result:** User C (Level 1) receives an email instantly. User D (Level 2) does NOT receive an email until it is their turn.
* **Status:** **PASS** (Enforced active-line sequential routing).

### Test Case 4: Internal Inbox Notifications (No External Email)
* **Action:** Ensure User C has no external email address set in their Odoo profile, and trigger an approval.
* **Expected Result:** User C still successfully receives the notification in their internal Odoo Inbox (speech bubble icon).
* **Status:** **PASS** (Removed strict email filters to allow internal routing).

### Test Case 5: Auto-Approval Security Bypass
* **Action:** Log in as User D (Level 2) and click the "Approve" button while Level 1 (User C) is still pending.
* **Expected Result:** The system successfully approves Level 2, and intelligently "Auto-Approves" Level 1, bypassing strict record rules.
* **Status:** **PASS** (Added `sudo()` execution for background auto-approvals).

### Test Case 6: Immutable Audit Trail Generation
* **Action:** Verify the "Audit Trail" tab after User D approves the request.
* **Expected Result:** The system successfully logs the approval actions (and auto-approvals), even though User D is a standard approver without manual log creation rights.
* **Status:** **PASS** (Elevated privileges for background log generation).

### Test Case 7: Chatter Personalization Tracking
* **Action:** Execute a "Force Approve" that notifies 4 different users, and check the record chatter.
* **Expected Result:** The system generates 4 separate, personalized emails in the chatter to ensure each user receives a secure, uniquely hashed action URL.
* **Status:** **PASS** (Verified as intended cryptographic security behavior).

### Test Case 8: UI Button Visibility
* **Action:** Review the header buttons on an "Approved" request.
* **Expected Result:** Buttons like "Submit", "Force Approve", and "Cancel" are dynamically hidden, leaving only valid actions like "Open Record".
* **Status:** **PASS** (Applied state-based `invisible` domains).

### Test Case 9: Core Document Security
* **Action:** Log in as User A (Standard User without Sales rights) and click "Open Record" on the approval request.
* **Expected Result:** Odoo successfully blocks User A with an Access Error, ensuring the approval module does not bypass core Sales Order security.
* **Status:** **PASS** (Verified as standard Odoo security).

### Test Case 10: Data Privacy for Standard Approvers
* **Action:** Log in as User A (Standard Approver) and attempt to locate User F's request.
* **Expected Result:** The request is completely hidden from User A because they are neither the requester nor an assigned approver.
* **Status:** **PASS** (Enforced by `Approval Request user scope` record rule).

### Test Case 11: Administrator Dashboard Visibility
* **Action:** Log in as User A (Administrator) and check the Dynamic Approval Dashboard.
* **Expected Result:** The "My Pending Approvals" menu remains empty (clean inbox), but User A can view all company requests via the "All Approvals" menu.
* **Status:** **PASS**

### Test Case 12: Manager Read-Only Department Visibility
* **Action:** Log in as User B (Manager Read-Only) who shares a Department with User F.
* **Expected Result:** User B can click the "All Approvals" menu and successfully view User F's request as an observer, without gaining manual approval rights.
* **Status:** **PASS** (Exposed "All Approvals" menu to the Manager Read-Only group and verified department record rules).

### Test Case 13: Alternative Approver Delegation
* **Action:** Configure an Alternative Approver for a level. Set the primary approver to be inactive/on leave, force a Python code failure, or allow the escalation timeout to expire.
* **Expected Result:** The engine intelligently bypasses the primary approver, activates the Alternative Approver, and sends a specialized "Escalated" email template.
* **Status:** **PASS** (Verified all 3 fallback conditions and cron job timeout).

### Test Case 14: Delegate Audit Trail
* **Action:** Have the Alternative Approver approve or refuse a request on behalf of the primary approver.
* **Expected Result:** The module logs the action in the Approval History with a distinct note indicating it was a "Delegated action" via the alternative approver.
* **Status:** **PASS** (Configured specific logging conditions in python engine).

### Test Case 15: Dynamic UI Field Visibility
* **Action:** Open the Approval Level configuration and change the "Approval Method" dropdown between Group, Job Position, and Dynamic Code.
* **Expected Result:** The corresponding configuration fields automatically hide and show to match the selected method, keeping the UI clean.
* **Status:** **PASS** (Applied XML `invisible` attributes).

### Test Case 16: Menu & Layout Optimization
* **Action:** Review the Dynamic Approval menu items and the Approval Type form view.
* **Expected Result:** Redundant menus (Approved/Refused) and unused tabs (Available Fields) are completely removed to streamline the user experience.
* **Status:** **PASS**

### Test Case 17: Dynamic Email Template Rendering
* **Action:** Trigger an approval request email notification to an approver.
* **Expected Result:** The email dynamically constructs an "Approval Status" history block, showing all previous level actions, explicitly bolding "Pending Your Approval" for the recipient's level, and including dynamic timeout text for alternative approvers.
* **Status:** **PASS** (Injected active line context into QWeb email rendering).

### Test Case 18: Multi-Method Approval Compatibility
* **Action:** Configure a 3-level approval workflow utilizing all three available methods: Level 1 (Dynamic Python Code), Level 2 (Role-Based Access Group), and Level 3 (Role-Based Job Position).
* **Expected Result:** The engine flawlessly resolves approvers for all three distinct methods sequentially. For Level 3, it successfully looks up all active employees holding the specified Job Position and resolves their corresponding Odoo user accounts.
* **Status:** **PASS** (Code natively extracts active users mapped to the `hr.employee` job position).
