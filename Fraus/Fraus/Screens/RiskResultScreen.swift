import SwiftUI

struct RiskResultScreen: View {
    let result: VerificationResult
    let onTransferToAI: () -> Void
    let onReturnHome: () -> Void

    private var bannerColor: Color {
        switch result.state {
        case .verified:
            return AppTheme.Colors.success
        case .suspicious:
            return AppTheme.Colors.danger
        case .unknown:
            return AppTheme.Colors.accentSecondary
        }
    }

    private var badgeStyle: StatusBadgeStyle {
        switch result.state {
        case .verified:
            return .success
        case .suspicious:
            return .danger
        case .unknown:
            return .info
        }
    }

    private var shouldShowTransfer: Bool {
        result.state == .suspicious || result.state == .unknown
    }

    private var statusSummary: String {
        switch result.state {
        case .verified:
            return "Trusted / Safe"
        case .suspicious:
            return "Critical / Dangerous"
        case .unknown:
            return "Unknown / Caution"
        }
    }

    var body: some View {
        AppScaffold(title: "Risk Result") {
            AppCard(title: result.phoneNumber, subtitle: "Caller analyzed") {
                VStack(alignment: .leading, spacing: AppTheme.Spacing.element) {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(result.state.title)
                            .font(.title2.bold())
                            .foregroundStyle(AppTheme.Colors.textPrimary)
                            .accessibilityIdentifier("riskResult.stateTitle")

                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(bannerColor.opacity(0.22))
                            .overlay(
                                RoundedRectangle(cornerRadius: 12, style: .continuous)
                                    .stroke(bannerColor, lineWidth: 1)
                            )
                            .frame(height: 74)
                            .overlay(
                                HStack {
                                    StatusBadge(text: result.state.title, style: badgeStyle)
                                    Spacer()
                                    if let confidence = result.confidence {
                                        Text("Confidence \(confidence)%")
                                            .foregroundStyle(AppTheme.Colors.textPrimary)
                                            .font(.headline.monospacedDigit())
                                    } else {
                                        Text(statusSummary)
                                            .foregroundStyle(AppTheme.Colors.textPrimary)
                                            .font(.headline)
                                    }
                                }
                                .padding(.horizontal, 12)
                            )
                    }

                    Text(result.explanation)
                        .foregroundStyle(AppTheme.Colors.textSecondary)
                        .accessibilityIdentifier("riskResult.explanation")

                    if result.sourceLabel != nil || result.riskLevel != nil {
                        HStack(spacing: 8) {
                            if let sourceLabel = result.sourceLabel {
                                StatusBadge(text: sourceLabel, style: .info)
                            }
                            if let riskLevel = result.riskLevel {
                                StatusBadge(text: "Risk: \(riskLevel.uppercased())", style: badgeStyle)
                            }
                        }
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Threat Tags")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(AppTheme.Colors.textSecondary)

                        ForEach(result.threatTags) { tag in
                            HStack {
                                StatusBadge(
                                    text: tag.severity.rawValue.capitalized,
                                    style: tag.severity == .high ? .danger : (tag.severity == .medium ? .warning : .info)
                                )
                                Text(tag.label)
                                    .foregroundStyle(AppTheme.Colors.textPrimary)
                                    .font(.subheadline)
                            }
                        }
                    }

                    if shouldShowTransfer {
                        PrimaryButton(title: "Transfer to AI Protection", action: onTransferToAI)
                    } else {
                        SecondaryButton(title: "Return to Home", action: onReturnHome)
                    }
                }
            }
        }
    }
}
