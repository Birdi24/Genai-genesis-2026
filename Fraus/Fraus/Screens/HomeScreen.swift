import SwiftUI

struct HomeScreen: View {
    let userName: String
    let onCheckCaller: () -> Void
    let onOpenAIAgent: () -> Void
    let onProfile: () -> Void
    let demoIncomingCalls: [DemoCallSession]
    let onTriggerIncomingCall: (DemoCallSession) -> Void

    private let stats: [HomeStatItem] = [
        HomeStatItem(title: "Calls Screened", value: "147", trend: "+12 today"),
        HomeStatItem(title: "Threats Blocked", value: "23", trend: "3 this week"),
        HomeStatItem(title: "Protection Score", value: "94%", trend: "Excellent")
    ]

    private let activity: [HomeActivityItem] = [
        HomeActivityItem(phoneNumber: "+1 (555) 012-3456", timeLabel: "2 min ago", risk: .low),
        HomeActivityItem(phoneNumber: "+1 (900) 555-0199", timeLabel: "15 min ago", risk: .critical),
        HomeActivityItem(phoneNumber: "+1 (312) 555-8877", timeLabel: "1 hr ago", risk: .medium)
    ]

    var body: some View {
        AppScaffold(title: "Home", showsTitle: false) {
            headerSection

            HStack(spacing: 10) {
                ForEach(stats) { item in
                    HomeStatCard(item: item)
                        .frame(maxWidth: .infinity)
                }
            }

            sectionTitle("Quick Actions")
            HStack(spacing: 12) {
                HomeQuickActionCard(
                    iconName: "checkmark.shield.fill",
                    title: "Verify Number",
                    subtitle: "Screen caller risk",
                    action: onCheckCaller
                )

                HomeQuickActionCard(
                    iconName: "brain.head.profile",
                    title: "AI Agent",
                    subtitle: "Start protection",
                    action: onOpenAIAgent
                )
            }

            sectionTitle("Demo Incoming Calls")
            Text("Simulate suspicious incoming calls and hand them off to AI protection")
                .foregroundStyle(AppTheme.Colors.textSecondary)
                .font(.caption)
                .padding(.top, -6)
            VStack(spacing: 10) {
                ForEach(demoIncomingCalls) { session in
                    HomeIncomingCallRow(session: session) {
                        onTriggerIncomingCall(session)
                    }
                }
            }

            sectionTitle("Recent Activity")
            VStack(spacing: 10) {
                ForEach(activity) { item in
                    HomeRecentActivityRow(item: item)
                }
            }

            SecondaryButton(title: "Profile", action: onProfile)
        }
    }

    private var headerSection: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Good afternoon,")
                    .foregroundStyle(AppTheme.Colors.textSecondary)
                    .font(.subheadline)

                Text(userName)
                    .foregroundStyle(AppTheme.Colors.textPrimary)
                    .font(.system(size: 34, weight: .bold, design: .rounded))
            }

            Spacer()
            ProtectedStatusPill()
        }
    }

    private func sectionTitle(_ title: String) -> some View {
        Text(title)
            .foregroundStyle(AppTheme.Colors.textPrimary)
            .font(.title3.weight(.semibold))
            .padding(.top, 4)
    }
}

private struct HomeIncomingCallRow: View {
    let session: DemoCallSession
    let action: () -> Void

    private var style: StatusBadgeStyle {
        switch session.callCategory {
        case .scam:
            return .danger
        case .unknown:
            return .warning
        }
    }

    private var label: String {
        session.callerLabel
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: "phone.fill")
                    .foregroundStyle(AppTheme.Colors.textSecondary)
                    .font(.caption)
                    .padding(8)
                    .background(AppTheme.Colors.surface)
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 4) {
                    Text(label)
                        .foregroundStyle(AppTheme.Colors.textPrimary)
                        .font(.subheadline.weight(.semibold))
                    Text(session.phoneNumber)
                        .foregroundStyle(AppTheme.Colors.textSecondary)
                        .font(.caption.monospacedDigit())
                }
                Spacer()
                StatusBadge(text: "Incoming Call", style: style)
            }

            HomeIncomingCallCTAButton(title: "Answer in Fraus") {
                action()
            }
        }
        .padding(14)
        .background(AppTheme.Colors.surfaceStrong)
        .overlay(
            RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous)
                .stroke(AppTheme.Colors.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous))
    }
}

private struct HomeIncomingCallCTAButton: View {
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(AppTheme.Colors.textPrimary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 11)
                .background(
                    LinearGradient(
                        colors: [AppTheme.Colors.accentSecondary, AppTheme.Colors.accent],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .overlay(
                    RoundedRectangle(cornerRadius: AppTheme.Radius.button, style: .continuous)
                        .stroke(Color.white.opacity(0.16), lineWidth: 1)
                )
                .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.button, style: .continuous))
                .shadow(color: AppTheme.Colors.accentGlow.opacity(0.28), radius: 14, x: 0, y: 6)
        }
        .buttonStyle(.plain)
    }
}

private struct HomeStatItem: Identifiable {
    let title: String
    let value: String
    let trend: String

    var id: String { title }
}

private enum HomeRiskLevel: String {
    case low = "LOW"
    case medium = "MEDIUM"
    case critical = "CRITICAL"

    var badgeStyle: StatusBadgeStyle {
        switch self {
        case .low:
            return .success
        case .medium:
            return .warning
        case .critical:
            return .danger
        }
    }
}

private struct HomeActivityItem: Identifiable {
    let phoneNumber: String
    let timeLabel: String
    let risk: HomeRiskLevel

    var id: String { "\(phoneNumber)-\(timeLabel)" }
}

private struct ProtectedStatusPill: View {
    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(AppTheme.Colors.success)
                .frame(width: 8, height: 8)
            Text("Protected")
                .foregroundStyle(AppTheme.Colors.textPrimary)
                .font(.caption.weight(.semibold))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(AppTheme.Colors.surfaceStrong)
        .overlay(
            Capsule()
                .stroke(AppTheme.Colors.borderStrong, lineWidth: 1)
        )
        .clipShape(Capsule())
        .shadow(color: AppTheme.Colors.accentGlow.opacity(0.2), radius: 10, x: 0, y: 4)
    }
}

private struct HomeStatCard: View {
    let item: HomeStatItem

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(item.title)
                .foregroundStyle(AppTheme.Colors.textSecondary)
                .font(.caption.weight(.semibold))
                .lineLimit(1)
                .minimumScaleFactor(0.8)

            Text(item.value)
                .foregroundStyle(AppTheme.Colors.textPrimary)
                .font(.system(size: 24, weight: .bold, design: .rounded))
                .lineLimit(1)

            Text(item.trend)
                .foregroundStyle(AppTheme.Colors.accentSecondary)
                .font(.caption)
                .lineLimit(1)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.Colors.surfaceStrong)
        .overlay(
            RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous)
                .stroke(AppTheme.Colors.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous))
        .shadow(color: AppTheme.Colors.shadow.opacity(0.65), radius: 10, x: 0, y: 6)
    }
}

private struct HomeQuickActionCard: View {
    let iconName: String
    let title: String
    let subtitle: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 10) {
                Image(systemName: iconName)
                    .font(.system(size: 30, weight: .semibold))
                    .foregroundStyle(AppTheme.Colors.accentSecondary)

                Text(title)
                    .foregroundStyle(AppTheme.Colors.textPrimary)
                    .font(.headline)

                Text(subtitle)
                    .foregroundStyle(AppTheme.Colors.textSecondary)
                    .font(.caption)
            }
            .padding(14)
            .frame(maxWidth: .infinity, minHeight: 132, alignment: .leading)
            .background(AppTheme.Colors.surfaceStrong)
            .overlay(
                RoundedRectangle(cornerRadius: AppTheme.Radius.card, style: .continuous)
                    .stroke(AppTheme.Colors.borderStrong, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.card, style: .continuous))
            .shadow(color: AppTheme.Colors.shadow.opacity(0.65), radius: 12, x: 0, y: 7)
        }
        .buttonStyle(.plain)
    }
}

private struct HomeRecentActivityRow: View {
    let item: HomeActivityItem

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            VStack(alignment: .leading, spacing: 4) {
                Text(item.phoneNumber)
                    .foregroundStyle(AppTheme.Colors.textPrimary)
                    .font(.subheadline.weight(.semibold))
                Text(item.timeLabel)
                    .foregroundStyle(AppTheme.Colors.textSecondary)
                    .font(.caption)
            }

            Spacer()
            StatusBadge(text: item.risk.rawValue, style: item.risk.badgeStyle)
        }
        .padding(14)
        .background(AppTheme.Colors.surfaceStrong)
        .overlay(
            RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous)
                .stroke(AppTheme.Colors.border, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous))
    }
}
