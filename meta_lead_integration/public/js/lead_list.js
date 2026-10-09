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
            msg += `<hr><h5 style="margin-bottom: 12px; font-weight: 600;">Failed Leads Details</h5>
            <div style="max-height: 400px; overflow: auto; border: 1px solid var(--border-color); border-radius: 4px;">
                <table class="table table-bordered table-sm" style="font-size: 12px; margin-bottom: 0; min-width: 850px;">
                    <thead style="background: var(--bg-light-gray, #f8f9fa); position: sticky; top: 0; z-index: 1;">
                        <tr>
                            <th style="min-width: 140px;">Meta Lead ID</th>
                            <th style="min-width: 120px;">Name</th>
                            <th style="min-width: 160px;">Email</th>
                            <th style="min-width: 110px;">Reason</th>
                            <th style="min-width: 250px;">Error</th>
                            <th style="min-width: 120px;">Ad Info</th>
                        </tr>
                    </thead>
                    <tbody>`;
            
            summary.failed_details.forEach(d => {
                let ad_info = [d.ad_id, d.adset_id, d.campaign_id].filter(Boolean).join("<br>");
                msg += `<tr>
                    <td><code>${d.meta_lead_id || ''}</code></td>
                    <td><b>${frappe.utils.escape_html(d.lead_name || '')}</b></td>
                    <td>${frappe.utils.escape_html(d.email || '')}</td>
                    <td><span class="badge badge-warning" style="color: #856404; background-color: #fff3cd;">${frappe.utils.escape_html(d.reason || '')}</span></td>
                    <td style="color: var(--text-danger, #e24c4c); font-family: monospace; font-size: 11px; white-space: pre-wrap; word-break: break-word;">${frappe.utils.escape_html(d.error || '')}</td>
                    <td style="font-size: 11px; color: var(--text-muted);">${ad_info}</td>
                </tr>`;
            });
            
            msg += `</tbody></table></div>`;
        }

        let d = frappe.msgprint({
            title: __('Meta Sync Summary'),
            message: msg,
            indicator: summary.failed > 0 ? 'orange' : 'green',
            wide: true
        });

        // Ensure the dialog modal is wide enough for full readability
        if (d && d.$wrapper) {
            d.$wrapper.find('.modal-dialog').css({
                'max-width': '950px',
                'width': '90%'
            });
        }
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
