import SwiftUI

struct AppScaffold<Content: View>: View {
    let title: String
    let showsTitle: Bool
    @ViewBuilder let content: Content

    init(title: String, showsTitle: Bool = true, @ViewBuilder content: () -> Content) {
        self.title = title
        self.showsTitle = showsTitle
        self.content = content()
    }

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [AppTheme.Colors.backgroundTop, AppTheme.Colors.backgroundBottom],
                startPoint: .top,
                endPoint: .bottom
            )
                .ignoresSafeArea()

            Circle()
                .fill(AppTheme.Colors.accent.opacity(0.08))
                .frame(width: 260, height: 260)
                .blur(radius: 80)
                .offset(x: 120, y: -280)
                .allowsHitTesting(false)

            ScrollView {
                VStack(alignment: .leading, spacing: AppTheme.Spacing.section) {
                    if showsTitle {
                        Text(title)
                            .font(.system(size: 34, weight: .bold, design: .rounded))
                            .foregroundStyle(AppTheme.Colors.textPrimary)
                    }

                    content
                }
                .padding(AppTheme.Spacing.screen)
            }
        }
        .navigationBarTitleDisplayMode(.inline)
    }
}
