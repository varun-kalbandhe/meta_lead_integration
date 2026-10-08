import frappe
import requests
from werkzeug.wrappers import Response

def _create_lead_from_data(meta_lead_id, field_data, created_time=None):
    # Check if lead already exists
    existing = frappe.db.exists("Lead", {"custom_meta_lead_id": meta_lead_id})
    if existing:
        return {"status": "exists", "lead": existing}

    # Map Meta data to ERPNext Lead fields
    lead_doc = frappe.new_doc("Lead")
    lead_doc.custom_meta_lead_id = meta_lead_id
    
    if created_time:
        from frappe.utils import get_datetime
        try:
            lead_doc.custom_meta_lead_created_time = get_datetime(created_time)
        except Exception:
            pass
    
    # Defaults in case not provided
    lead_doc.lead_name = "Unknown Lead"
    
    from frappe.utils import strip_html_tags
    
    for field in field_data:
        name = field.get("name")
        values = field.get("values", [])
        if not values:
            continue
            
        value = str(values[0])
        value = strip_html_tags(value).strip()
        
        if not value:
            continue
            
        if name == "full_name":
            lead_doc.lead_name = value
        elif name == "first_name":
            if lead_doc.lead_name == "Unknown Lead":
                lead_doc.lead_name = value
        elif name == "last_name":
            # Just append to whatever we have if it's not unknown
            pass
        elif name == "email":
            lead_doc.email_id = value
        elif name == "phone":
            lead_doc.mobile_no = value
        elif name == "website":
            lead_doc.website = value
        elif name == "what_industry_does_your_business_belong_to?":
            lead_doc.custom_industry = value
        elif name == "what_software_are_you_currently_using?":
            lead_doc.custom_current_software = value
        elif name == "when_are_you_planning_to_implement_erp?":
            lead_doc.custom_erp_implementation_timeline = value
            
    if not lead_doc.lead_name:
        lead_doc.lead_name = "Unknown Lead"

    # Check for duplicate email before inserting
    if lead_doc.email_id:
        existing_email_lead = frappe.db.get_value("Lead", {"email_id": lead_doc.email_id}, "name")
        if existing_email_lead:
            return {"status": "email_exists", "lead": existing_email_lead}
            
    # Insert Lead
    try:
        lead_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {"status": "created", "lead": lead_doc.name}
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(f"Error creating lead: {str(e)}")

@frappe.whitelist()
def fetch_and_create_lead(meta_lead_id):
    # Retrieve token from settings
    settings = frappe.get_single("Meta Integration Settings")
    token = settings.get_password("access_token")
    if not token:
        frappe.throw("Meta Access Token is missing in Meta Integration Settings.")
        
    # Check if lead already exists
    existing = frappe.db.exists("Lead", {"custom_meta_lead_id": meta_lead_id})
    if existing:
        return {"status": "exists", "lead": existing}
        
    # Fetch lead from Meta Graph API
    url = f"https://graph.facebook.com/v19.0/{meta_lead_id}"
    params = {
        "access_token": token,
        "fields": "created_time,field_data"
    }
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        frappe.throw(f"Failed to fetch Meta Lead: {response.text}")
        
    data = response.json()
    field_data = data.get("field_data", [])
    created_time = data.get("created_time")
    
    return _create_lead_from_data(meta_lead_id, field_data, created_time)


@frappe.whitelist(allow_guest=True)
def webhook():
    if frappe.request.method == "GET":
        mode = frappe.form_dict.get("hub.mode")
        token = frappe.form_dict.get("hub.verify_token")
        challenge = frappe.form_dict.get("hub.challenge")

        if mode == "subscribe" and token:
            settings = frappe.get_single("Meta Integration Settings")
            verify_token = settings.get_password("webhook_verify_token")
            
            if token == verify_token:
                frappe.logger("meta_integration").info("Webhook verified successfully.")
                return Response(challenge or "", status=200, mimetype="text/plain")
            else:
                frappe.logger("meta_integration").warning("Webhook verification failed.")
                return Response("Verification token mismatch", status=403, mimetype="text/plain")
                
        return Response("Bad request", status=400, mimetype="text/plain")

    elif frappe.request.method == "POST":
        try:
            payload = frappe.request.get_json()
            frappe.logger("meta_integration").info("Webhook POST received.")
            
            # Extract leadgen_id
            if payload and payload.get("object") == "page":
                for entry in payload.get("entry", []):
                    for change in entry.get("changes", []):
                        if change.get("field") == "leadgen":
                            value = change.get("value", {})
                            leadgen_id = value.get("leadgen_id")
                            if leadgen_id:
                                # Process it
                                result = fetch_and_create_lead(leadgen_id)
                                frappe.logger("meta_integration").info(f"Processed leadgen_id {leadgen_id}: {result}")
                                
            return Response("EVENT_RECEIVED", status=200, mimetype="text/plain")
            
        except Exception as e:
            frappe.logger("meta_integration").error(f"Error processing webhook: {str(e)}")
            return Response("Internal Server Error", status=500, mimetype="text/plain")

@frappe.whitelist()
def sync_historical_leads(from_date=None):
    frappe.enqueue(
        "meta_lead_integration.meta_lead_integration.api.run_sync_historical_leads_job",
        user=frappe.session.user,
        from_date=from_date,
        queue="default",
        timeout=1500
    )
    return "started"

def run_sync_historical_leads_job(user, from_date=None):
    settings = frappe.get_single("Meta Integration Settings")
    token = settings.get_password("access_token")
    form_ids = settings.get("lead_form_id")
    
    summary = {
        "created": 0,
        "already_exists": 0,
        "email_duplicate": 0,
        "failed": 0,
        "failed_details": []
    }
    
    if not token or not form_ids:
        frappe.publish_realtime("meta_lead_sync_complete", summary, user=user)
        return
        
    import json
    import datetime
    
    from_timestamp = None
    if from_date:
        try:
            dt = datetime.datetime.strptime(from_date, "%Y-%m-%d")
            from_timestamp = int(dt.timestamp())
        except Exception:
            pass

    form_ids_list = [f.strip() for f in form_ids.split(",") if f.strip()]
    
    for form_id in form_ids_list:
        url = f"https://graph.facebook.com/v19.0/{form_id}/leads"
        params = {"access_token": token, "limit": 100, "fields": "id,created_time,field_data,ad_id,adset_id,campaign_id"}
        
        if from_timestamp:
            params["filtering"] = json.dumps([
                {"field": "time_created", "operator": "GREATER_THAN_OR_EQUAL", "value": from_timestamp}
            ])
        
        while url:
            try:
                response = requests.get(url, params=params)
                if response.status_code != 200:
                    frappe.logger("meta_integration").error(f"Failed to fetch leads for form {form_id}: {response.text}")
                    break
                    
                data = response.json()
                leads = data.get("data", [])
                
                for lead in leads:
                    lead_id = lead.get("id")
                    if not lead_id:
                        continue
                        
                    # Skip if already in DB to save API calls
                    if frappe.db.exists("Lead", {"custom_meta_lead_id": lead_id}):
                        summary["already_exists"] += 1
                        continue
                        
                    # Call direct logic with field_data
                    try:
                        result = _create_lead_from_data(lead_id, lead.get("field_data", []), lead.get("created_time"))
                        status = result.get("status")
                        if status == "created":
                            summary["created"] += 1
                        elif status == "exists":
                            summary["already_exists"] += 1
                        elif status == "email_exists":
                            summary["email_duplicate"] += 1
                    except Exception as e:
                        frappe.logger("meta_integration").error(f"Failed to process lead {lead_id}: {str(e)}")
                        
                        # Extract basic info for the error report
                        lead_name = "Unknown"
                        email = "Unknown"
                        for f in lead.get("field_data", []):
                            name = f.get("name")
                            values = f.get("values", [])
                            if values:
                                if name in ["full_name", "first_name"]:
                                    lead_name = values[0]
                                elif name == "email":
                                    email = values[0]
                                    
                        summary["failed"] += 1
                        summary["failed_details"].append({
                            "meta_lead_id": lead_id,
                            "lead_name": lead_name,
                            "email": email,
                            "reason": "Creation Error",
                            "error": str(e),
                            "ad_id": lead.get("ad_id"),
                            "adset_id": lead.get("adset_id"),
                            "campaign_id": lead.get("campaign_id")
                        })
                        
                # Pagination
                paging = data.get("paging", {})
                next_url = paging.get("next")
                if next_url:
                    url = next_url
                    params = {} # The next_url usually contains the access_token and cursors already
                else:
                    url = None
            except Exception as e:
                frappe.logger("meta_integration").error(f"Sync error: {str(e)}")
                break
                
    frappe.publish_realtime("meta_lead_sync_complete", summary, user=user)
