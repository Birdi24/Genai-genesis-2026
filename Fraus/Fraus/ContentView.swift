//
//  ContentView.swift
//  Fraus
//
//  Created by Parth Narkhede on 2026-03-14.
//

import SwiftUI

struct AppView: View {
    @State private var path: [AppRoute] = []
    @StateObject private var demoCallSessionManager = DemoCallSessionManager()
    private let mockUserName = "Parth"
    private let incomingCallService: SimulatedIncomingCallServicing = SimulatedIncomingCallService()
    private let aiAgentEntryResult = VerificationResult(
        phoneNumber: "+1 (900) 555-0199",
        state: .suspicious,
        explanation: "High-risk behavior detected. Transfer to AI agent is recommended.",
        threatTags: [
            ThreatTag(label: "Impersonation Risk", severity: .high),
            ThreatTag(label: "Urgency Pressure", severity: .high)
        ],
        confidence: nil,
        sourceLabel: "Fraus Verification Engine",
        riskLevel: "high"
    )
    
    var body: some View {
        NavigationStack(path: $path) {
            WelcomeScreen(
                onLogin: { path.append(.login) },
                onSignUp: { path.append(.signup) }
            )
            .navigationDestination(for: AppRoute.self) { route in
                switch route {
                case .welcome:
                    WelcomeScreen(
                        onLogin: { path.append(.login) },
                        onSignUp: { path.append(.signup) }
                    )
                case .login:
                    LoginScreen(
                        onContinue: { path.append(.home) },
                        onCreateAccount: { path.append(.signup) }
                    )
                case .signup:
                    SignUpScreen(
                        onCreate: { path.append(.home) },
                        onLogin: { path.append(.login) }
                    )
                case .home:
                    HomeScreen(
                        userName: mockUserName,
                        onCheckCaller: {
                            demoCallSessionManager.clear()
                            path.append(.verifyCaller(nil, nil, nil))
                        },
                        onOpenAIAgent: {
                            demoCallSessionManager.clear()
                            path.append(.transferToAI(aiAgentEntryResult))
                        },
                        onProfile: { path.append(.profile) },
                        demoIncomingCalls: incomingCallService.demoIncomingCalls(),
                        onTriggerIncomingCall: { session in
                            demoCallSessionManager.beginSession(from: session)
                            if let active = demoCallSessionManager.activeSession {
                                path.append(.verifyCaller(active.phoneNumber, active.callerLabel, active.callCategory))
                            }
                        }
                    )
                case .verifyCaller(let prefilledPhoneNumber, let callerLabel, let callCategory):
                    VerifyCallerScreen(
                        prefilledPhoneNumber: prefilledPhoneNumber,
                        prefilledCallerLabel: callerLabel,
                        prefilledCallCategory: callCategory,
                        onStartVerification: {
                            demoCallSessionManager.markVerifying()
                        }
                    ) { result in
                        demoCallSessionManager.applyVerificationResult(result)
                        path.append(.riskResult(result))
                    }
                case .riskResult(let result):
                    RiskResultScreen(
                        result: result,
                        onTransferToAI: {
                            demoCallSessionManager.markTransferred()
                            path.append(.transferToAI(result))
                        },
                        onReturnHome: {
                            demoCallSessionManager.markCompleted()
                            demoCallSessionManager.clear()
                            path.removeAll()
                            path.append(.home)
                        }
                    )
                case .transferToAI(let result):
                    TransferToAIScreen(
                        verificationResult: result,
                        demoCallSession: demoCallSessionManager.activeSession
                    ) { session in
                        demoCallSessionManager.markActiveProtection()
                        path.append(.activeProtection(session))
                    }
                case .activeProtection(let session):
                    ActiveProtectionScreen(session: session) {
                        demoCallSessionManager.markCompleted()
                        demoCallSessionManager.clear()
                        path.removeAll()
                        path.append(.home)
                    }
                case .profile:
                    ProfileScreen()
                }
            }
        }
        .tint(AppTheme.Colors.accent)
        .preferredColorScheme(.dark)
    }
}

enum AppRoute: Hashable {
    case welcome
    case login
    case signup
    case home
    case verifyCaller(String?, String?, DemoCallCategory?)
    case riskResult(VerificationResult)
    case transferToAI(VerificationResult)
    case activeProtection(ProtectionSession)
    case profile
}

struct WelcomeScreen: View {
    let onLogin: () -> Void
    let onSignUp: () -> Void

    var body: some View {
        AppScaffold(title: "Welcome") {
            AppCard(title: "Fraus Security", subtitle: "Premium caller intelligence") {
                VStack(alignment: .leading, spacing: AppTheme.Spacing.element) {
                    Text("Bank-grade protection for suspicious calls, with AI takeover when risk is detected.")
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.Colors.textSecondary)

                    HStack(spacing: 8) {
                        StatusBadge(text: "AI Ready", style: .success)
                        StatusBadge(text: "Privacy First", style: .info)
                    }

                    PrimaryButton(title: "Log In", action: onLogin)
                    SecondaryButton(title: "Create Account", action: onSignUp)
                }
            }
        }
    }
}

struct LoginScreen: View {
    let onContinue: () -> Void
    let onCreateAccount: () -> Void

    @State private var email = ""
    @State private var password = ""

    var body: some View {
        AppScaffold(title: "Login") {
            AppCard(title: "Sign in", subtitle: "Secure access to protection dashboard") {
                VStack(spacing: AppTheme.Spacing.element) {
                    FormInputField(title: "Email", placeholder: "name@example.com", text: $email)
                    FormInputField(title: "Password", placeholder: "••••••••", text: $password, isSecure: true)
                    StatusBadge(text: "Demo environment", style: .info)
                    PrimaryButton(title: "Continue", action: onContinue)
                    SecondaryButton(title: "Create Account", action: onCreateAccount)
                }
            }
        }
    }
}

struct SignUpScreen: View {
    let onCreate: () -> Void
    let onLogin: () -> Void

    @State private var fullName = ""
    @State private var email = ""
    @State private var password = ""

    var body: some View {
        AppScaffold(title: "Sign Up") {
            AppCard(title: "Create account", subtitle: "Set up your secure caller shield") {
                VStack(spacing: AppTheme.Spacing.element) {
                    FormInputField(title: "Full name", placeholder: "Jane Doe", text: $fullName)
                    FormInputField(title: "Email", placeholder: "name@example.com", text: $email)
                    FormInputField(title: "Password", placeholder: "••••••••", text: $password, isSecure: true)
                    StatusBadge(text: "Identity check required", style: .warning)
                    PrimaryButton(title: "Create Account", action: onCreate)
                    SecondaryButton(title: "Already have an account? Log In", action: onLogin)
                }
            }
        }
    }
}

struct ProfileScreen: View {
    var body: some View {
        AppScaffold(title: "Profile") {
            AppCard(title: "Account", subtitle: "Security profile") {
                VStack(alignment: .leading, spacing: AppTheme.Spacing.element) {
                    profileRow(label: "Name", value: "Parth Narkhede")
                    profileRow(label: "Email", value: "parth@example.com")
                    profileRow(label: "Protection Tier", value: "Fraus Premium")
                    StatusBadge(text: "Read-only demo", style: .neutral)
                }
            }
        }
    }

    private func profileRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .foregroundStyle(AppTheme.Colors.textSecondary)
            Spacer()
            Text(value)
                .foregroundStyle(AppTheme.Colors.textPrimary)
                .font(.subheadline.weight(.semibold))
        }
    }
}

#Preview {
    AppView()
}
