frappe.listview_settings['Lead'] = frappe.listview_settings['Lead'] || {};
let original_onload = frappe.listview_settings['Lead'].onload;

frappe.listview_settings['Lead'].onload = function(listview) {
    if (original_onload) {
        original_onload(listview);
    }
    
    frappe.realtime.on('meta_lead_sync_complete', (summary) => {
        let msg = `
            <div style="font-size: 14px;">
                <b>Sync Complete!</b><br><br>
                <ul>
                    <li><b>Created:</b> ${summary.created}</li>
                    <li><b>Already Synced:</b> ${summary.already_exists}</li>
                    <li><b>Email Duplicate:</b> ${summary.email_duplicate}</li>
                    <li><b>Failed:</b> ${summary.failed}</li>
                </ul>
            </div>
        `;
        frappe.msgprint({
            title: __('Meta Sync Summary'),
            message: msg,
            indicator: 'green'
        });
        listview.refresh();
    });
    
    listview.page.add_inner_button(__('Sync Leads from Meta'), function() {
        frappe.call({
            method: 'meta_lead_integration.meta_lead_integration.api.sync_historical_leads',
            freeze: true,
            freeze_message: __('Starting Meta Lead Sync...'),
            callback: function(r) {
                frappe.show_alert({
                    message: __('Meta Lead Sync started in background.'),
                    indicator: 'info'
                });
            }
        });
    });
};
