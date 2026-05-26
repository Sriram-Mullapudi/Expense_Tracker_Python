"""Production deployment verification script and checklist."""
import os
import sys
import subprocess
import requests
from datetime import datetime
from typing import Dict, List, Tuple, Optional


class DeploymentVerifier:
    """Verify production deployment readiness and health."""

    def __init__(self, base_url: str = 'http://localhost:5000'):
        """
        Initialize deployment verifier.
        
        Args:
            base_url: Base URL of the deployed application
        """
        self.base_url = base_url.rstrip('/')
        self.results: Dict[str, Dict] = {}
        self.start_time = datetime.now()

    def check_server_health(self) -> bool:
        """Check if server is responding."""
        try:
            response = requests.get(f'{self.base_url}/health', timeout=5)
            success = response.status_code == 200
            self.results['server_health'] = {
                'status': 'PASS' if success else 'FAIL',
                'details': f'Status code: {response.status_code}'
            }
            return success
        except Exception as e:
            self.results['server_health'] = {
                'status': 'FAIL',
                'details': str(e)
            }
            return False

    def check_database_connection(self) -> bool:
        """Verify database connectivity."""
        try:
            response = requests.get(f'{self.base_url}/api/health/db', timeout=5)
            success = response.status_code == 200
            self.results['database'] = {
                'status': 'PASS' if success else 'FAIL',
                'details': response.json() if success else response.text
            }
            return success
        except Exception as e:
            self.results['database'] = {
                'status': 'FAIL',
                'details': str(e)
            }
            return False

    def check_auth_endpoints(self) -> bool:
        """Verify authentication endpoints are working."""
        try:
            # Test login endpoint
            response = requests.post(
                f'{self.base_url}/api/auth/login',
                json={'username': 'test', 'password': 'test'},
                timeout=5
            )
            # We expect 401 (bad credentials) not 404 or 500
            success = response.status_code in [401, 400]
            self.results['auth_endpoints'] = {
                'status': 'PASS' if success else 'FAIL',
                'details': f'Login endpoint responded with {response.status_code}'
            }
            return success
        except Exception as e:
            self.results['auth_endpoints'] = {
                'status': 'FAIL',
                'details': str(e)
            }
            return False

    def check_static_files(self) -> bool:
        """Verify static files are being served."""
        try:
            response = requests.get(f'{self.base_url}/static/style.css', timeout=5)
            success = response.status_code == 200
            self.results['static_files'] = {
                'status': 'PASS' if success else 'FAIL',
                'details': f'CSS file status: {response.status_code}'
            }
            return success
        except Exception as e:
            self.results['static_files'] = {
                'status': 'FAIL',
                'details': str(e)
            }
            return False

    def check_error_handling(self) -> bool:
        """Verify error handling (404, 500)."""
        try:
            # Test 404
            response = requests.get(f'{self.base_url}/nonexistent', timeout=5)
            has_404 = response.status_code == 404
            
            self.results['error_handling'] = {
                'status': 'PASS' if has_404 else 'FAIL',
                'details': f'404 handling status: {response.status_code}'
            }
            return has_404
        except Exception as e:
            self.results['error_handling'] = {
                'status': 'FAIL',
                'details': str(e)
            }
            return False

    def check_security_headers(self) -> bool:
        """Verify security headers are present."""
        try:
            response = requests.get(f'{self.base_url}/', timeout=5)
            headers = response.headers
            
            security_checks = {
                'X-Content-Type-Options': 'nosniff' in headers.get('X-Content-Type-Options', ''),
                'X-Frame-Options': 'DENY' in headers.get('X-Frame-Options', ''),
                'X-XSS-Protection': '1' in headers.get('X-XSS-Protection', ''),
            }
            
            passed = sum(1 for v in security_checks.values() if v)
            total = len(security_checks)
            
            self.results['security_headers'] = {
                'status': 'PASS' if passed >= 2 else 'WARN' if passed >= 1 else 'FAIL',
                'details': f'{passed}/{total} security headers present: {security_checks}'
            }
            return passed >= 2
        except Exception as e:
            self.results['security_headers'] = {
                'status': 'FAIL',
                'details': str(e)
            }
            return False

    def check_ssl_certificate(self) -> bool:
        """Verify SSL certificate is valid (if HTTPS)."""
        try:
            if not self.base_url.startswith('https'):
                self.results['ssl_certificate'] = {
                    'status': 'SKIP',
                    'details': 'Not HTTPS'
                }
                return True
            
            response = requests.get(self.base_url, timeout=5, verify=True)
            success = response.status_code < 500
            
            self.results['ssl_certificate'] = {
                'status': 'PASS' if success else 'FAIL',
                'details': 'SSL certificate is valid'
            }
            return success
        except requests.exceptions.SSLError as e:
            self.results['ssl_certificate'] = {
                'status': 'FAIL',
                'details': f'SSL error: {str(e)}'
            }
            return False
        except Exception as e:
            self.results['ssl_certificate'] = {
                'status': 'FAIL',
                'details': str(e)
            }
            return False

    def check_environment_variables(self) -> bool:
        """Verify required environment variables are set."""
        required_vars = [
            'SECRET_KEY',
            'FLASK_ENV',
            'SQLALCHEMY_DATABASE_URI',
        ]
        
        optional_vars = [
            'SENTRY_DSN',
            'MAIL_SERVER',
            'JWT_SECRET',
        ]
        
        missing_required = [v for v in required_vars if not os.getenv(v)]
        missing_optional = [v for v in optional_vars if not os.getenv(v)]
        
        success = len(missing_required) == 0
        
        self.results['environment_variables'] = {
            'status': 'PASS' if success else 'FAIL',
            'details': {
                'missing_required': missing_required,
                'missing_optional': missing_optional
            }
        }
        return success

    def check_dependencies(self) -> bool:
        """Verify critical dependencies are installed."""
        try:
            import flask
            import flask_sqlalchemy
            import flask_login
            import flask_mail
            
            critical_deps = {
                'Flask': flask.__version__,
                'Flask-SQLAlchemy': flask_sqlalchemy.__version__,
                'Flask-Login': flask_login.__version__,
                'Flask-Mail': flask_mail.__version__,
            }
            
            self.results['dependencies'] = {
                'status': 'PASS',
                'details': critical_deps
            }
            return True
        except ImportError as e:
            self.results['dependencies'] = {
                'status': 'FAIL',
                'details': f'Missing dependency: {str(e)}'
            }
            return False

    def run_all_checks(self) -> Tuple[bool, Dict]:
        """
        Run all deployment checks.
        
        Returns:
            Tuple of (all_passed, results_dict)
        """
        print(f"🚀 Starting deployment verification at {self.start_time.isoformat()}")
        print(f"📍 Target: {self.base_url}\n")
        
        checks = [
            ('Environment Variables', self.check_environment_variables),
            ('Dependencies', self.check_dependencies),
            ('Server Health', self.check_server_health),
            ('Database Connection', self.check_database_connection),
            ('Auth Endpoints', self.check_auth_endpoints),
            ('Static Files', self.check_static_files),
            ('Error Handling', self.check_error_handling),
            ('Security Headers', self.check_security_headers),
            ('SSL Certificate', self.check_ssl_certificate),
        ]
        
        results = []
        for check_name, check_func in checks:
            try:
                result = check_func()
                status = self.results.get(check_name.lower().replace(' ', '_'), {}).get('status', 'UNKNOWN')
                print(f"{'✓' if status == 'PASS' else '✗' if status == 'FAIL' else '⊘'} {check_name}: {status}")
                results.append(result)
            except Exception as e:
                print(f"✗ {check_name}: ERROR - {str(e)}")
                results.append(False)
        
        print(f"\n📊 Results: {sum(results)}/{len(results)} checks passed")
        print(f"⏱️  Completed in {(datetime.now() - self.start_time).total_seconds():.2f}s")
        
        return all(results), self.results

    def export_report(self, filepath: str = 'deployment_report.json') -> None:
        """Export verification results to JSON."""
        import json
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\n📄 Report exported to {filepath}")


# ============================================================================
# PRODUCTION DEPLOYMENT CHECKLIST
# ============================================================================

PRODUCTION_CHECKLIST = """
╔════════════════════════════════════════════════════════════════════════════╗
║           EXPENSE TRACKER - PRODUCTION DEPLOYMENT CHECKLIST               ║
╚════════════════════════════════════════════════════════════════════════════╝

PRE-DEPLOYMENT
===============
□ Code review completed and approved
□ All tests passing (pytest coverage > 80%)
□ No security vulnerabilities detected (Bandit, Safety)
□ Database migrations tested
□ Secrets/API keys NOT committed to repo
□ Environment variables documented
□ Rollback plan documented
□ Incident response team notified

DEPLOYMENT ENVIRONMENT
======================
□ Production server provisioned and hardened
□ Python 3.9+ installed
□ Database configured and accessible
□ Redis/Cache configured (if using)
□ Email service configured and tested
□ Sentry DSN configured
□ File upload directory exists with proper permissions
□ SSL certificate installed and valid
□ DNS records updated (if domain changing)
□ Load balancer configured (if applicable)
□ Firewall rules configured (port 80, 443)
□ Log rotation configured

APPLICATION CONFIGURATION
==========================
□ DEBUG = False in production config
□ SECRET_KEY set to strong random value (32+ chars)
□ FLASK_ENV = 'production'
□ SQLALCHEMY_DATABASE_URI points to production DB
□ JWT_SECRET configured
□ MAIL_SERVER configured with production SMTP
□ SENTRY_DSN configured
□ APP_URL set correctly
□ SESSION_COOKIE_SECURE = True
□ SESSION_COOKIE_HTTPONLY = True
□ FORCE_HTTPS = True (redirect HTTP to HTTPS)

DATABASE
========
□ Database backed up
□ All migrations applied
□ Database indexes created
□ Connection pooling configured
□ Query logging enabled
□ Database monitoring alerts configured

SECURITY
========
□ HTTPS enabled and enforced
□ Security headers configured (CSP, HSTS, X-Frame-Options, etc.)
□ CORS properly configured (only allowed origins)
□ Rate limiting enabled
□ Input validation enabled
□ SQL injection prevention verified
□ XSS protection verified
□ CSRF protection enabled
□ Authentication/Authorization tested
□ 2FA enabled for admin users
□ Password hashing verified (bcrypt)
□ API keys/tokens not exposed in logs
□ Secrets not in environment variables (use secret manager)

MONITORING & LOGGING
====================
□ Centralized logging configured
□ Error tracking (Sentry) active
□ Application performance monitoring (APM) configured
□ Log aggregation service configured
□ Alerts configured for:
    □ High error rates
    □ Database connection issues
    □ Disk space warnings
    □ CPU/Memory thresholds
    □ Security incidents
□ Dashboard configured for real-time monitoring
□ Health check endpoint accessible

PERFORMANCE
===========
□ Database query performance tested
□ Caching strategy implemented
□ Static files optimized (minified, gzipped)
□ CDN configured (if applicable)
□ Database connection pooling configured
□ API response times acceptable
□ Load testing completed
□ Memory usage within limits
□ Database backups automated

BACKUP & DISASTER RECOVERY
===========================
□ Automated daily backups configured
□ Backup restoration tested
□ Database point-in-time recovery possible
□ Off-site backup storage configured
□ Disaster recovery plan documented
□ RTO (Recovery Time Objective) defined
□ RPO (Recovery Point Objective) defined

DOCUMENTATION
==============
□ Deployment instructions documented
□ Configuration documented
□ Runbook for common issues created
□ Emergency contact list documented
□ Escalation procedures documented
□ Known issues/limitations documented

CI/CD
=====
□ GitHub Actions workflow running successfully
□ Automated tests passing
□ Code quality checks passing
□ Security scanning enabled
□ Deployment pipeline automated
□ Rollback procedure automated

DEPLOYMENT DAY
==============
□ Maintenance window scheduled
□ Team assembled and briefed
□ Monitoring dashboards open
□ Communication channels active (Slack, PagerDuty)
□ Deployment started
□ Health checks passed
□ Smoke tests passed
□ Users notified
□ Performance monitored
□ Incident response on standby

POST-DEPLOYMENT (First 24 hours)
=================================
□ No critical errors in logs
□ Database performing well
□ API response times normal
□ Users reporting no issues
□ Email notifications working
□ File uploads working
□ Session management working
□ Auth/2FA working
□ Payment processing (if applicable) working
□ All background jobs running
□ Backups completing successfully
□ Sentry error tracking working
□ APM metrics normal

WEEK 1 POST-DEPLOYMENT
======================
□ User feedback collected and reviewed
□ Performance metrics analyzed
□ Security audit completed
□ Cost analysis performed (cloud resources)
□ Auto-scaling tested (if applicable)
□ Disaster recovery test performed
□ Documentation updated with lessons learned
□ Post-mortem meeting scheduled (if issues occurred)

╔════════════════════════════════════════════════════════════════════════════╗
║  Sign-off: ________________  Date: ________  Environment: ________________ ║
╚════════════════════════════════════════════════════════════════════════════╝
"""


def main():
    """Run deployment verification."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Deployment verification')
    parser.add_argument('--url', default='http://localhost:5000',
                       help='Base URL to verify')
    parser.add_argument('--checklist', action='store_true',
                       help='Print deployment checklist')
    parser.add_argument('--report', default='deployment_report.json',
                       help='File to save report')
    
    args = parser.parse_args()
    
    if args.checklist:
        print(PRODUCTION_CHECKLIST)
        return 0
    
    verifier = DeploymentVerifier(base_url=args.url)
    all_passed, results = verifier.run_all_checks()
    verifier.export_report(args.report)
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
