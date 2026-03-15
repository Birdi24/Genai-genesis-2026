import SwiftUI

enum AppTheme {
    enum Colors {
        static let background = Color(red: 0.04, green: 0.06, blue: 0.06)
        static let backgroundTop = Color(red: 0.06, green: 0.09, blue: 0.09)
        static let backgroundBottom = Color(red: 0.02, green: 0.03, blue: 0.03)

        static let surface = Color(red: 0.09, green: 0.12, blue: 0.12)
        static let surfaceElevated = Color(red: 0.12, green: 0.16, blue: 0.15)
        static let surfaceStrong = Color(red: 0.14, green: 0.19, blue: 0.18)

        static let accent = Color(red: 0.05, green: 0.64, blue: 0.34)
        static let accentSecondary = Color(red: 0.30, green: 0.74, blue: 0.53)
        static let accentMuted = Color(red: 0.21, green: 0.44, blue: 0.35)
        static let accentGlow = Color(red: 0.12, green: 0.78, blue: 0.43)

        static let textPrimary = Color.white
        static let textSecondary = Color(red: 0.73, green: 0.77, blue: 0.79)
        static let textTertiary = Color(red: 0.52, green: 0.57, blue: 0.60)

        static let success = Color(red: 0.15, green: 0.75, blue: 0.42)
        static let warning = Color(red: 0.89, green: 0.66, blue: 0.20)
        static let danger = Color(red: 0.90, green: 0.28, blue: 0.31)

        static let border = Color.white.opacity(0.10)
        static let borderStrong = Color.white.opacity(0.18)
        static let shadow = Color.black.opacity(0.55)
    }

    enum Radius {
        static let card: CGFloat = 20
        static let input: CGFloat = 14
        static let button: CGFloat = 15
        static let badge: CGFloat = 9
        static let pill: CGFloat = 999
    }

    enum Spacing {
        static let screen: CGFloat = 22
        static let cardPadding: CGFloat = 18
        static let section: CGFloat = 18
        static let element: CGFloat = 12
        static let compact: CGFloat = 8
        static let large: CGFloat = 24
    }

    enum Shadow {
        static let radius: CGFloat = 18
        static let y: CGFloat = 10
        static let glowRadius: CGFloat = 20
    }
}
