import SwiftUI

struct IncomingCallDemoScreen: View {
    let callSession: DemoCallSession
    let onCheckCaller: () -> Void
    let onDismiss: () -> Void

    private var statusStyle: StatusBadgeStyle {
        if callSession.callCategory == .scam {
            return .danger
        }
        return .warning
    }

    private var callerHeadline: String {
        callSession.callerLabel
    }

    var body: some View {
        AppScaffold(title: "Incoming Call") {
            AppCard(title: "Fraus Incoming Alert", subtitle: "In-app call simulation") {
                VStack(alignment: .leading, spacing: AppTheme.Spacing.element) {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(callerHeadline)
                                .foregroundStyle(AppTheme.Colors.textPrimary)
                                .font(.title3.weight(.semibold))
                            Text(callSession.phoneNumber)
                                .foregroundStyle(AppTheme.Colors.textSecondary)
                                .font(.headline.monospacedDigit())
                        }

                        Spacer()
                        StatusBadge(text: callSession.status.title, style: statusStyle)
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Live Transcript Preview")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(AppTheme.Colors.textSecondary)

                        ForEach(Array(callSession.transcriptLines.prefix(2).enumerated()), id: \.offset) { _, line in
                            Text("• \(line)")
                                .font(.subheadline)
                                .foregroundStyle(AppTheme.Colors.textPrimary)
                        }
                    }

                    HStack(spacing: 10) {
                        SecondaryButton(title: "Dismiss", action: onDismiss)
                        PrimaryButton(title: "Check Caller", action: onCheckCaller)
                    }

                    Text("This is a simulated in-app call for demo use. Not native iPhone call UI.")
                        .font(.caption)
                        .foregroundStyle(AppTheme.Colors.textSecondary)
                }
            }
        }
    }
}
