import SwiftUI

struct TransferToAIScreen: View {
    let verificationResult: VerificationResult
    let demoCallSession: DemoCallSession?
    let onSessionStarted: (ProtectionSession) -> Void

    @State private var isConnecting = false
    private let mockFactory = MockProtectionSessionFactory()

    init(
        verificationResult: VerificationResult,
        demoCallSession: DemoCallSession?,
        onSessionStarted: @escaping (ProtectionSession) -> Void
    ) {
        self.verificationResult = verificationResult
        self.demoCallSession = demoCallSession
        self.onSessionStarted = onSessionStarted
    }

    var body: some View {
        AppScaffold(title: "Transfer to AI") {
            AppCard(title: "Explicit AI Handoff", subtitle: verificationResult.phoneNumber) {
                VStack(alignment: .leading, spacing: AppTheme.Spacing.element) {
                    Text("Fraus does not listen by default. You are explicitly authorizing AI protection to take over this suspicious interaction.")
                        .foregroundStyle(AppTheme.Colors.textSecondary)

                    VStack(alignment: .leading, spacing: 10) {
                        transferStep(number: "1", text: "AI agent answers and engages the caller")
                        transferStep(number: "2", text: "Session intelligence streams to fraud analysis")
                        transferStep(number: "3", text: "Threat entities are extracted for backend graphing")
                    }

                    if isConnecting {
                        HStack(spacing: 10) {
                            ProgressView()
                                .tint(AppTheme.Colors.accent)
                            Text("Connecting AI Protection...")
                                .foregroundStyle(AppTheme.Colors.textPrimary)
                        }
                    }

                    PrimaryButton(title: isConnecting ? "Connecting..." : "Start AI Protection") {
                        guard !isConnecting else { return }
                        isConnecting = true

                        Task {
                            try? await Task.sleep(nanoseconds: 900_000_000)
                            let session = mockFactory.makeSession(
                                for: verificationResult,
                                callSession: demoCallSession
                            )
                            onSessionStarted(session)
                            isConnecting = false
                        }
                    }
                    .opacity(isConnecting ? 0.7 : 1)
                    .disabled(isConnecting)
                }
            }
        }
    }

    private func transferStep(number: String, text: String) -> some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(AppTheme.Colors.accent)
                Text(number)
                    .font(.caption.bold())
                    .foregroundStyle(AppTheme.Colors.textPrimary)
            }
            .frame(width: 24, height: 24)

            Text(text)
                .font(.subheadline)
                .foregroundStyle(AppTheme.Colors.textPrimary)

            Spacer()
        }
        .padding(10)
        .background(AppTheme.Colors.surfaceStrong)
        .overlay(
            RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous)
                .stroke(AppTheme.Colors.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous))
    }

}
