"""
Audit Routes - Dashboard, real-time monitoring, and export endpoints
Part 1: Dashboard Data Endpoints
Part 2: Real-time Monitoring (WebSocket)
Part 3: Export Capabilities
"""
from flask import jsonify, request, render_template
from flask_login import login_required, current_user
from . import audit_bp
from .analytics import ActivityAnalytics, AlertSystem, ReportGenerator
from audit_log import read_audit_logs
import json


# ============================================
# DASHBOARD PAGE ROUTES
# ============================================

@audit_bp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    """Display audit dashboard page"""
    try:
        # Admin only
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        return render_template('audit-dashboard.html')
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@audit_bp.route('/monitor', methods=['GET'])
@login_required
def monitor():
    """Display live monitoring page"""
    try:
        # Admin only
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        return render_template('audit-monitor.html')
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@audit_bp.route('/export', methods=['GET'])
@login_required
def export_page():
    """Display export and reporting page"""
    try:
        # Admin only
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        return render_template('audit-export.html')
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# PART 1: DASHBOARD DATA ENDPOINTS
# ============================================

@audit_bp.route('/dashboard-data', methods=['GET'])
@login_required
def get_dashboard_data():
    """Get aggregated dashboard data"""
    try:
        # Admin only
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        # Get time range from query params
        days = request.args.get('days', 7, type=int)
        
        data = {
            'quick_stats': ActivityAnalytics.get_quick_stats(),
            'activity_trend': ActivityAnalytics.get_activity_trend(days=days),
            'failed_login_trend': ActivityAnalytics.get_failed_login_stats(days=days),
            'user_activity': ActivityAnalytics.get_user_activity_chart(limit=10),
            'ip_statistics': ActivityAnalytics.get_ip_statistics(limit=10),
            'action_distribution': ActivityAnalytics.get_action_distribution(),
            'recent_activity': ActivityAnalytics.get_recent_activity(limit=50)
        }
        
        return jsonify({
            'success': True,
            'data': data,
            'timestamp': json.dumps({'iso': __import__('datetime').datetime.now().isoformat()})
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@audit_bp.route('/activity-trend', methods=['GET'])
@login_required
def get_activity_trend():
    """Get activity trend data"""
    try:
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        days = request.args.get('days', 7, type=int)
        action = request.args.get('action', None, type=str)
        
        trend = ActivityAnalytics.get_activity_trend(days=days, action_filter=action)
        
        return jsonify({
            'success': True,
            'data': trend
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@audit_bp.route('/ip-statistics', methods=['GET'])
@login_required
def get_ip_stats():
    """Get IP statistics"""
    try:
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        limit = request.args.get('limit', 10, type=int)
        
        stats = ActivityAnalytics.get_ip_statistics(limit=limit)
        
        return jsonify({
            'success': True,
            'data': stats
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@audit_bp.route('/quick-stats', methods=['GET'])
@login_required
def get_quick_stats():
    """Get quick statistics"""
    try:
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        stats = ActivityAnalytics.get_quick_stats()
        
        return jsonify({
            'success': True,
            'data': stats
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@audit_bp.route('/recent-activity', methods=['GET'])
@login_required
def get_recent_activity():
    """Get recent activity events"""
    try:
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        limit = request.args.get('limit', 50, type=int)
        
        activity = ActivityAnalytics.get_recent_activity(limit=limit)
        
        return jsonify({
            'success': True,
            'count': len(activity),
            'data': activity
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# PART 2: REAL-TIME MONITORING
# ============================================

@audit_bp.route('/alerts/check', methods=['GET'])
@login_required
def check_alerts():
    """Check for active alerts"""
    try:
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        alerts = []
        
        # Check failed login spike
        spike_alert = AlertSystem.check_failed_login_spike(minutes=1)
        if spike_alert.get('alert'):
            alerts.append(spike_alert)
        
        # Check blocked IPs
        blocked_alert = AlertSystem.check_blocked_ips()
        if blocked_alert.get('alert'):
            alerts.append(blocked_alert)
        
        return jsonify({
            'success': True,
            'alerts': alerts,
            'has_alerts': len(alerts) > 0
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@audit_bp.route('/alerts/config', methods=['GET', 'POST'])
@login_required
def alert_config():
    """Get or set alert thresholds"""
    try:
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        if request.method == 'GET':
            return jsonify({
                'success': True,
                'thresholds': AlertSystem.THRESHOLDS
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            
            # Update thresholds
            if 'failed_logins_per_minute' in data:
                AlertSystem.THRESHOLDS['failed_logins_per_minute'] = data['failed_logins_per_minute']
            if 'failed_logins_per_hour' in data:
                AlertSystem.THRESHOLDS['failed_logins_per_hour'] = data['failed_logins_per_hour']
            if 'blocked_ips' in data:
                AlertSystem.THRESHOLDS['blocked_ips'] = data['blocked_ips']
            
            return jsonify({
                'success': True,
                'message': 'Alert thresholds updated',
                'thresholds': AlertSystem.THRESHOLDS
            })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# PART 3: EXPORT CAPABILITIES
# ============================================

@audit_bp.route('/filters', methods=['GET'])
@login_required
def get_filters():
    """Get available filters for reports"""
    try:
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        filters = ReportGenerator.get_available_filters()
        
        return jsonify({
            'success': True,
            'filters': filters
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@audit_bp.route('/export/preview', methods=['POST'])
@login_required
def export_preview():
    """Get preview of filtered data"""
    try:
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        filters = request.get_json().get('filters', {})
        limit = request.get_json().get('limit', 100)
        
        logs = read_audit_logs(limit=10000)
        filtered_logs = ReportGenerator.apply_filters(logs, filters)
        preview = filtered_logs[:limit]
        
        return jsonify({
            'success': True,
            'total_records': len(filtered_logs),
            'preview_count': len(preview),
            'data': preview
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@audit_bp.route('/export/csv', methods=['POST'])
@login_required
def export_csv():
    """Export filtered data as CSV"""
    try:
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        filters = request.get_json().get('filters', {})
        
        logs = read_audit_logs(limit=10000)
        filtered_logs = ReportGenerator.apply_filters(logs, filters)
        
        # Generate CSV
        import csv
        import io
        from datetime import datetime
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['timestamp', 'username', 'action', 'ip_address', 'level'])
        writer.writeheader()
        
        for log in filtered_logs:
            writer.writerow({
                'timestamp': log.get('timestamp', ''),
                'username': log.get('username', ''),
                'action': log.get('action', ''),
                'ip_address': log.get('ip_address', ''),
                'level': log.get('level', 'INFO')
            })
        
        csv_data = output.getvalue()
        
        return jsonify({
            'success': True,
            'data': csv_data,
            'record_count': len(filtered_logs),
            'filename': f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@audit_bp.route('/export/json', methods=['POST'])
@login_required
def export_json():
    """Export filtered data as JSON"""
    try:
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        filters = request.get_json().get('filters', {})
        
        logs = read_audit_logs(limit=10000)
        filtered_logs = ReportGenerator.apply_filters(logs, filters)
        
        from datetime import datetime
        
        export_data = {
            'export_date': datetime.now().isoformat(),
            'filters_applied': filters,
            'record_count': len(filtered_logs),
            'data': filtered_logs
        }
        
        return jsonify({
            'success': True,
            'data': export_data,
            'filename': f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@audit_bp.route('/export/pdf', methods=['POST'])
@login_required
def export_pdf():
    """Export filtered data as PDF"""
    try:
        if current_user.id != '1':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        filters = request.get_json().get('filters', {})
        
        logs = read_audit_logs(limit=10000)
        filtered_logs = ReportGenerator.apply_filters(logs, filters)
        
        from datetime import datetime
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        import io
        
        # Create PDF in memory
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        elements = []
        
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], 
                                     fontSize=24, textColor=colors.HexColor('#1f77b4'),
                                     spaceAfter=30)
        elements.append(Paragraph('Audit Report', title_style))
        elements.append(Spacer(1, 12))
        
        # Report info
        report_info = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>Records: {len(filtered_logs)}"
        elements.append(Paragraph(report_info, styles['Normal']))
        elements.append(Spacer(1, 12))
        
        # Create table data
        table_data = [['Timestamp', 'User', 'Action', 'IP', 'Level']]
        
        for log in filtered_logs[:100]:  # Limit to 100 rows in PDF
            table_data.append([
                log.get('timestamp', '')[:19],
                log.get('username', '')[:15],
                log.get('action', '')[:30],
                log.get('ip_address', '')[:15],
                log.get('level', 'INFO')[:8]
            ])
        
        # Create table
        table = Table(table_data, colWidths=[1.5*inch, 1.2*inch, 2*inch, 1.2*inch, 0.8*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        pdf_content = pdf_buffer.getvalue()
        
        return jsonify({
            'success': True,
            'message': 'PDF generated successfully',
            'record_count': len(filtered_logs),
            'filename': f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
