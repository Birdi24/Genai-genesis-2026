import SwiftUI

struct FormInputField: View {
    let title: String
    let placeholder: String
    @Binding var text: String
    var isSecure: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.Colors.textSecondary)

            Group {
                if isSecure {
                    SecureField(placeholder, text: $text)
                        .textInputAutocapitalization(.never)
                } else {
                    TextField(placeholder, text: $text)
                        .textInputAutocapitalization(.never)
                }
            }
            .padding(14)
            .background(AppTheme.Colors.surfaceStrong)
            .overlay(
                RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous)
                    .stroke(AppTheme.Colors.borderStrong, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous))
            .foregroundStyle(AppTheme.Colors.textPrimary)
            .font(.subheadline)
        }
    }
}
