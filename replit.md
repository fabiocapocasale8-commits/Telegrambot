# Overview

Plasma Bot is a Discord selfbot with licensing functionality that uses a Telegram bot for secure authentication. The project implements a dual-architecture system where users authenticate via Telegram to obtain Discord bot access. **Updated: Now uses Telegram bot for seamless authentication instead of command line prompts.** The system includes license validation, user session management, and an admin server for license key management.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Authentication Flow
The system uses a multi-stage authentication process:
- **Telegram Bot Authentication**: Primary entry point where users provide license keys and Discord tokens
- **Remote License Validation**: Validates license keys against a remote API server
- **Discord Bot Activation**: Launches the main Discord selfbot after successful authentication

## License Management System
The project implements a comprehensive license validation system:
- **Remote API Architecture**: License validation is performed via HTTP requests to a remote server rather than local file storage
- **Hardware-based Licensing**: Each license is tied to specific hardware IDs to prevent sharing
- **Encrypted Key Storage**: License keys are stored in encrypted format using Fernet encryption
- **Time-based Access Control**: Supports 7-day, 30-day, and permanent license types

## Discord Bot Framework
The main bot functionality includes:
- **Command System**: Custom prefix-based command handling (default prefix: ".")
- **Auto-messaging Features**: Automated channel messaging and auto-reply functionality
- **AFK System**: Away-from-keyboard message handling
- **Copycat Features**: Message mirroring capabilities
- **Configuration Management**: Per-user config files based on token hash

## Admin Server Architecture
Separate Flask-based admin panel for license management:
- **RESTful API**: HTTP endpoints for license validation and user management
- **Session-based Admin Panel**: Web interface for creating and managing license keys
- **Secure Token Authentication**: API token-based authentication for client requests
- **CORS Support**: Cross-origin resource sharing for web-based management

## Data Storage Strategy
The system uses multiple storage approaches:
- **JSON Configuration Files**: User-specific settings stored in config directory
- **Encrypted License Database**: Secure storage of license keys and user data
- **Environment Variables**: Sensitive tokens and API endpoints
- **Session Management**: In-memory user session tracking for Telegram bot

## Error Handling and Resilience
Implements multiple fallback mechanisms:
- **API Timeout Handling**: 10-second timeouts for license validation requests
- **Graceful Degradation**: System continues operation with local fallbacks when possible
- **Token Validation**: Pre-flight checks for required environment variables

# External Dependencies

## Core Libraries
- **discord.py-self**: Discord API interaction for selfbot functionality
- **python-telegram-bot**: Telegram Bot API for authentication interface
- **Flask**: Web framework for admin server and API endpoints
- **cryptography**: Encryption and secure key management
- **requests**: HTTP client for remote license validation

## Additional Utilities
- **colorama**: Terminal color output for enhanced user experience
- **gtts**: Google Text-to-Speech for voice message generation
- **qrcode**: QR code generation functionality
- **pyfiglet**: ASCII art text rendering

## Development Dependencies
- **flask-cors**: Cross-origin resource sharing support
- **secrets**: Cryptographically secure random number generation

## External Services Integration
- **License API Server**: Remote validation service (configurable endpoint)
- **Discord API**: Primary bot functionality platform
- **Telegram Bot API**: Authentication and user interaction interface