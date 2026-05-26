"""File upload routes for receipt management."""
from flask import Blueprint, request, jsonify, send_from_directory, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Expense
from file_upload_service import (
    save_upload_file, delete_upload_file, get_file_url, file_exists
)

uploads_bp = Blueprint('uploads', __name__, url_prefix='/uploads')


@uploads_bp.route('/api/receipt', methods=['POST'])
@login_required
def upload_receipt():
    """Upload receipt file for an expense."""
    expense_id = request.form.get('expense_id', type=int)
    
    if not expense_id:
        return jsonify({'error': 'Missing expense_id'}), 400
    
    expense = Expense.query.get(expense_id)
    if not expense or expense.user_id != current_user.id:
        return jsonify({'error': 'Expense not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    filename, error = save_upload_file(file, current_user.id)
    
    if error:
        return jsonify({'error': error}), 400
    
    # Delete old receipt if exists
    if expense.receipt_path:
        delete_upload_file(expense.receipt_path)
    
    # Update expense with new receipt
    expense.receipt_path = filename
    db.session.commit()
    
    return jsonify({
        'success': True,
        'filename': filename,
        'url': get_file_url(filename)
    }), 201


@uploads_bp.route('/receipts/<filename>')
@login_required
def serve_receipt(filename):
    """Serve uploaded receipt file (with security checks)."""
    # Security: verify user owns this file (files are named with user_id prefix)
    if not filename.startswith(f"{current_user.id}_"):
        flash('Unauthorized', 'warning')
        return redirect(url_for('dashboard.index'))
    
    if not file_exists(filename):
        flash('File not found', 'danger')
        return redirect(url_for('dashboard.index'))
    
    return send_from_directory('uploads/receipts', filename)


@uploads_bp.route('/api/receipt/<int:expense_id>', methods=['DELETE'])
@login_required
def delete_receipt(expense_id):
    """Delete receipt file from expense."""
    expense = Expense.query.get(expense_id)
    if not expense or expense.user_id != current_user.id:
        return jsonify({'error': 'Expense not found'}), 404
    
    if expense.receipt_path:
        delete_upload_file(expense.receipt_path)
        expense.receipt_path = None
        db.session.commit()
        return jsonify({'success': True}), 200
    
    return jsonify({'error': 'No receipt attached'}), 400
