import SwiftUI

enum StatusBadgeStyle {
    case info
    case warning
    case success
    case danger
    case neutral

    var backgroundColor: Color {
        switch self {
        case .info:
            return AppTheme.Colors.accentMuted.opacity(0.35)
        case .warning:
            return AppTheme.Colors.warning.opacity(0.2)
        case .success:
            return AppTheme.Colors.success.opacity(0.2)
        case .danger:
            return AppTheme.Colors.danger.opacity(0.2)
        case .neutral:
            return AppTheme.Colors.surfaceElevated
        }
    }

    var foregroundColor: Color {
        switch self {
        case .info:
            return AppTheme.Colors.accentSecondary
        case .warning:
            return AppTheme.Colors.warning
        case .success:
            return AppTheme.Colors.success
        case .danger:
            return AppTheme.Colors.danger
        case .neutral:
            return AppTheme.Colors.textSecondary
        }
    }
}

struct StatusBadge: View {
    let text: String
    let style: StatusBadgeStyle

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .foregroundStyle(style.foregroundColor)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(style.backgroundColor)
            .overlay(
                RoundedRectangle(cornerRadius: AppTheme.Radius.badge, style: .continuous)
                    .stroke(style.foregroundColor.opacity(0.45), lineWidth: 0.8)
            )
            .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.badge, style: .continuous))
    }
}
