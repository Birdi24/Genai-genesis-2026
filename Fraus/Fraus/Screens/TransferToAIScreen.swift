import SwiftUI

struct TransferToAIScreen: View {
    let verificationResult: VerificationResult
    let demoCallSession: DemoCallSession?
    let onSessionStarted: (ProtectionSession) -> Void

    @State private var isConnecting = false
    @State private var errorMessage: String?
    private let takeoverService: TakeoverSessionServicing

    init(
        verificationResult: VerificationResult,
        demoCallSession: DemoCallSession?,
        takeoverService: TakeoverSessionServicing? = nil,
        onSessionStarted: @escaping (ProtectionSession) -> Void
    ) {
        self.verificationResult = verificationResult
        self.demoCallSession = demoCallSession
        self.takeoverService = takeoverService ?? TakeoverSessionService()
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

                    if let errorMessage {
                        Text(errorMessage)
                            .font(.footnote)
                            .foregroundStyle(AppTheme.Colors.warning)
                    }

                    PrimaryButton(title: isConnecting ? "Connecting..." : "Start AI Protection") {
                        guard !isConnecting else { return }
                        isConnecting = true
                        errorMessage = nil

                        Task {
                            let startedAt = Date()

                            do {
                                let session = try await takeoverService.startTakeover(
                                    verificationResult: verificationResult,
                                    demoCallSession: demoCallSession
                                )

                                await ensureMinimumLoadingDuration(from: startedAt)
                                onSessionStarted(session)
                                isConnecting = false
                            } catch {
                                await ensureMinimumLoadingDuration(from: startedAt)
                                isConnecting = false

                                if let localizedError = error as? LocalizedError,
                                   let description = localizedError.errorDescription {
                                    errorMessage = description
                                } else {
                                    errorMessage = "Unable to start AI protection right now."
                                }
                            }
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

    private func ensureMinimumLoadingDuration(from startDate: Date) async {
        let elapsed = Date().timeIntervalSince(startDate)
        let minimumDuration: TimeInterval = 0.8
        let remaining = minimumDuration - elapsed
        guard remaining > 0 else { return }
        try? await Task.sleep(nanoseconds: UInt64(remaining * 1_000_000_000))
    }
}
