import SwiftUI
import UIKit

struct VerifyCallerScreen: View {
    let prefilledPhoneNumber: String?
    let prefilledCallerLabel: String?
    let prefilledCallCategory: DemoCallCategory?
    let onStartVerification: (() -> Void)?
    let onResult: (VerificationResult) -> Void

    @StateObject private var viewModel: VerifyCallerViewModel

    private let sampleOptions: [SampleFillOption] = [
        SampleFillOption(
            title: "Verified (Chase)",
            phoneNumber: "+1 (800) 555-1234",
            hintColor: AppTheme.Colors.success
        ),
        SampleFillOption(
            title: "Scam",
            phoneNumber: "+1 (900) 555-0199",
            hintColor: AppTheme.Colors.danger
        ),
        SampleFillOption(
            title: "Unknown",
            phoneNumber: "+1 (312) 000-0000",
            hintColor: AppTheme.Colors.warning
        )
    ]

    init(
        prefilledPhoneNumber: String? = nil,
        prefilledCallerLabel: String? = nil,
        prefilledCallCategory: DemoCallCategory? = nil,
        onStartVerification: (() -> Void)? = nil,
        onResult: @escaping (VerificationResult) -> Void
    ) {
        self.prefilledPhoneNumber = prefilledPhoneNumber
        self.prefilledCallerLabel = prefilledCallerLabel
        self.prefilledCallCategory = prefilledCallCategory
        self.onStartVerification = onStartVerification
        self.onResult = onResult
        _viewModel = StateObject(wrappedValue: VerifyCallerViewModel(initialPhoneNumber: prefilledPhoneNumber))
    }

    var body: some View {
        AppScaffold(title: "Verify Caller") {
            AppCard(title: "Caller Number", subtitle: "Paste or enter a phone number") {
                VStack(spacing: AppTheme.Spacing.element) {
                    FormInputField(title: "Phone Number", placeholder: "+1 (555) 000-0000", text: $viewModel.phoneNumber)

                    if prefilledPhoneNumber != nil {
                        HStack(spacing: 8) {
                            StatusBadge(text: "Prefilled from incoming call", style: .info)
                            if let callerLabel = prefilledCallerLabel {
                                StatusBadge(text: callerLabel, style: .neutral)
                            }
                            if let category = prefilledCallCategory {
                                StatusBadge(
                                    text: category.title,
                                    style: category == .scam ? .danger : .warning
                                )
                            }
                        }
                    }

                    HStack(spacing: 10) {
                        SecondaryButton(title: "Paste") {
                            if let clipboard = UIPasteboard.general.string, !clipboard.isEmpty {
                                viewModel.setPhoneNumber(clipboard)
                            }
                        }

                        SecondaryButton(title: "Clear") {
                            viewModel.clearPhoneNumber()
                        }
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Try a sample number")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(AppTheme.Colors.textSecondary)

                        Text("Use sample numbers to demo trusted, suspicious, and unknown caller results.")
                            .font(.caption2)
                            .foregroundStyle(AppTheme.Colors.textTertiary)

                        LazyVGrid(
                            columns: [
                                GridItem(.flexible(), spacing: 8),
                                GridItem(.flexible(), spacing: 8),
                                GridItem(.flexible(), spacing: 8)
                            ],
                            spacing: 8
                        ) {
                            ForEach(sampleOptions) { option in
                            Button {
                                viewModel.setPhoneNumber(option.phoneNumber)
                            } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(option.title)
                                        .foregroundStyle(AppTheme.Colors.textPrimary)
                                        .font(.caption.weight(.semibold))
                                    Text(option.phoneNumber)
                                        .foregroundStyle(AppTheme.Colors.textSecondary)
                                        .font(.caption2.monospacedDigit())
                                        .lineLimit(1)
                                        .minimumScaleFactor(0.7)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 8)
                                .background(AppTheme.Colors.surfaceStrong)
                                .overlay(
                                    RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous)
                                        .stroke(option.hintColor.opacity(0.5), lineWidth: 1)
                                )
                                .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous))
                            }
                            .buttonStyle(.plain)
                            }
                        }
                    }

                    if let errorMessage = viewModel.errorMessage {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack(spacing: 8) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundStyle(AppTheme.Colors.warning)
                                Text(errorMessage)
                                    .foregroundStyle(AppTheme.Colors.textSecondary)
                                    .font(.caption)
                            }

                            SecondaryButton(title: "Retry") {
                                onStartVerification?()
                                viewModel.verifyNumber(onSuccess: onResult)
                            }
                        }
                    }

                    PrimaryButton(title: viewModel.isLoading ? "Checking..." : "Check Number") {
                        onStartVerification?()
                        viewModel.verifyNumber(onSuccess: onResult)
                    }
                    .opacity(viewModel.canSubmit ? 1 : 0.55)
                    .disabled(!viewModel.canSubmit)

                    if viewModel.isLoading {
                        HStack(spacing: 10) {
                            ProgressView()
                                .tint(AppTheme.Colors.accent)
                            Text("Verifying caller with fraud engine...")
                                .font(.caption)
                                .foregroundStyle(AppTheme.Colors.textSecondary)
                        }
                    }
                }
            }
        }
    }
}

private struct SampleFillOption: Identifiable {
    let title: String
    let phoneNumber: String
    let hintColor: Color

    var id: String { title }
}
