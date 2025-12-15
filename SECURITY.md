# Security Policy

## Supported Versions

LogView is currently in beta. Security updates will be provided for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.x.x   | :white_check_mark: |

## Security Principles

LogView is designed with security as a core principle:

### 1. **No Credential Storage**
- LogView **never** stores credentials, API keys, or secrets
- Authentication is delegated to existing tools:
  - GCP: Uses Application Default Credentials (ADC) via `gcloud auth application-default login`
  - GKE: Uses kubeconfig from `kubectl`
- Application logs are written to `~/.config/logview/logview.log` and **never** contain credentials or PII

### 2. **File Access Controls**
- **Directory Allowlist**: LogView restricts file access to explicitly permitted directories
- Default allowed directories: `/var/log`, `/opt`, `/home`
- **Path Traversal Prevention**: Malicious paths like `../../../etc/passwd` are blocked
- **Symlink Protection**: Symlinks pointing outside allowed directories are rejected
- Configure the allowlist in `~/.config/logview/config.json`:
  ```json
  {
    "discovery": {
      "allowed_directories": ["/var/log", "/opt/myapp/logs"]
    }
  }
  ```

### 3. **Input Sanitization**
- All user input is validated before constructing queries
- Log content is sanitized before display to prevent terminal escape sequence attacks
- No shell interpolation in any adapter

### 4. **Minimal Permissions**
- LogView requests only **read** access to log sources
- No write permissions required
- No privileged operations performed

### 5. **Secure Installation**
- Install script (`install.sh`) uses HTTPS for all downloads
- **Two-step install** method available for security review:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/agileguy/logview/main/install.sh -o install.sh
  less install.sh  # Review the script
  bash install.sh
  ```
- Checksum verification available for wheel packages (see README.md)

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in LogView, please report it privately:

1. **Email**: Create a private security advisory on GitHub:
   - Go to https://github.com/agileguy/logview/security/advisories
   - Click "New draft security advisory"
   - Provide details about the vulnerability

2. **What to Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if you have one)

3. **Response Timeline**:
   - **Initial Response**: Within 48 hours
   - **Status Update**: Within 7 days
   - **Fix Timeline**: Depends on severity
     - **Critical**: Within 7 days
     - **High**: Within 14 days
     - **Medium**: Within 30 days
     - **Low**: Next release

4. **Disclosure Policy**:
   - We follow coordinated disclosure
   - We will credit you in the security advisory (unless you prefer to remain anonymous)
   - We will notify you before public disclosure
   - We aim to release a fix before public disclosure

## Security Best Practices for Users

### 1. **Install from Trusted Sources**
- Use PyPI or GitHub releases only
- Verify checksums when downloading wheel files
- Review install.sh before executing (two-step install method)

### 2. **Restrict File Access**
- Configure `allowed_directories` to limit file system access
- For production systems, avoid allowing access to `/home`
- Use least-privilege principles

### 3. **Keep LogView Updated**
- Subscribe to GitHub releases for security updates
- Run `pipx upgrade logview` or `pip install --upgrade logview` regularly

### 4. **GCP/GKE Authentication**
- Use Application Default Credentials (ADC), never service account keys
- Follow the principle of least privilege for GCP IAM roles
- Minimum required role: `roles/logging.viewer`

### 5. **Review Application Logs**
- Monitor `~/.config/logview/logview.log` for suspicious activity
- Ensure log files don't contain sensitive information

### 6. **Multi-User Systems**
- Be aware that default `/home` allowlist grants access to all users' files
- Restrict to specific directories in production environments

## Security Audits

LogView undergoes regular security reviews:

- **Static Analysis**: shellcheck for shell scripts
- **Dependency Scanning**: Dependabot enabled for automatic vulnerability detection
- **Code Review**: All pull requests require review before merge
- **CI/CD Checks**: Automated linting, type checking, and testing

## Known Security Limitations

### 1. **Log Content Trust**
LogView displays log content as-is from the source. Malicious log content could potentially:
- Contain terminal escape sequences (mitigated by sanitization)
- Include misleading information
- Contain large volumes of data (mitigated by filtering and limits)

### 2. **Local File Access**
When configured to access local files:
- LogView runs with the user's permissions
- Can read any file the user has access to
- Default `/home` allowlist is permissive

### 3. **Cloud Provider Access**
When using GCP/GKE adapters:
- LogView inherits the user's cloud permissions
- No additional access controls beyond IAM
- Recommend using separate service accounts with minimal permissions

## Security Updates

Security updates will be released as:
1. **Patch releases** for critical vulnerabilities (e.g., 0.2.1)
2. **GitHub Security Advisories** for all security issues
3. **CHANGELOG.md** entries with `[SECURITY]` tag

Subscribe to:
- GitHub repository releases
- Security advisories at https://github.com/agileguy/logview/security/advisories

## Contact

For security questions or concerns that are not vulnerability reports:
- Open a GitHub Discussion
- Email: Use GitHub security advisory (private)

---

**Last Updated**: 2024-12-14
