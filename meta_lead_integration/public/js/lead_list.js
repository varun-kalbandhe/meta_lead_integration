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

        if (summary.failed > 0 && summary.failed_details && summary.failed_details.length > 0) {
            msg += `<hr><h5>Failed Leads Details</h5>
            <div style="max-height: 300px; overflow-y: auto;">
                <table class="table table-bordered table-sm" style="font-size: 12px;">
                    <thead>
                        <tr>
                            <th>Meta Lead ID</th>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Reason</th>
                            <th>Error</th>
                            <th>Ad Info</th>
                        </tr>
                    </thead>
                    <tbody>`;
            
            summary.failed_details.forEach(d => {
                let ad_info = [d.ad_id, d.adset_id, d.campaign_id].filter(Boolean).join("<br>");
                msg += `<tr>
                    <td>${d.meta_lead_id || ''}</td>
                    <td>${d.lead_name || ''}</td>
                    <td>${d.email || ''}</td>
                    <td>${d.reason || ''}</td>
                    <td style="color: red; word-break: break-all;">${d.error || ''}</td>
                    <td>${ad_info}</td>
                </tr>`;
            });
            
            msg += `</tbody></table></div>`;
        }

        frappe.msgprint({
            title: __('Meta Sync Summary'),
            message: msg,
            indicator: summary.failed > 0 ? 'orange' : 'green',
            wide: summary.failed > 0
        });
        listview.refresh();
    });
    
    listview.page.add_inner_button(__('Sync Leads from Meta'), function() {
        frappe.prompt([
            {
                fieldname: 'from_date',
                fieldtype: 'Date',
                label: __('Sync From Date'),
                description: __('Optional. Only sync leads generated on or after this date.'),
                reqd: 0
            }
        ], function(values) {
            frappe.call({
                method: 'meta_lead_integration.meta_lead_integration.api.sync_historical_leads',
                args: {
                    from_date: values.from_date
                },
                freeze: true,
                freeze_message: __('Starting Meta Lead Sync...'),
                callback: function(r) {
                    frappe.show_alert({
                        message: __('Meta Lead Sync started in background.'),
                        indicator: 'info'
                    });
                }
            });
        }, __('Sync Meta Leads'), __('Start Sync'));
    });
};
