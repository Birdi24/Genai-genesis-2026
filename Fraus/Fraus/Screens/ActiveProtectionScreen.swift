import SwiftUI

struct ActiveProtectionScreen: View {
    let onEndSession: () -> Void

    @StateObject private var viewModel: ActiveProtectionViewModel
    @State private var isPulsing = false
    @State private var isWaveAnimating = false

    init(session: ProtectionSession, onEndSession: @escaping () -> Void) {
        self.onEndSession = onEndSession
        _viewModel = StateObject(wrappedValue: ActiveProtectionViewModel(session: session))
    }

    var body: some View {
        AppScaffold(title: "Active Protection") {
            AppCard(title: "Connected Protection Session", subtitle: viewModel.activeSession.callerNumber) {
                VStack(alignment: .leading, spacing: AppTheme.Spacing.element) {
                    HStack(alignment: .center) {
                        HStack(spacing: 10) {
                            ZStack {
                                Circle()
                                    .fill(AppTheme.Colors.accentGlow.opacity(0.28))
                                    .frame(width: 30, height: 30)
                                    .scaleEffect(isPulsing ? 1.35 : 1)
                                    .opacity(isPulsing ? 0.75 : 0.35)

                                Circle()
                                    .fill(AppTheme.Colors.success)
                                    .frame(width: 11, height: 11)
                            }
                            .animation(.easeInOut(duration: 1).repeatForever(autoreverses: true), value: isPulsing)

                            Text("AI \(viewModel.connectionState.badgeText)")
                                .font(.title3.weight(.bold))
                                .foregroundStyle(AppTheme.Colors.textPrimary)
                        }

                        Spacer()
                        VStack(alignment: .trailing, spacing: 4) {
                            Text("Session Time")
                                .font(.caption)
                                .foregroundStyle(AppTheme.Colors.textSecondary)
                            Text(viewModel.formattedDuration)
                                .font(.system(size: 24, weight: .bold, design: .monospaced))
                                .foregroundStyle(AppTheme.Colors.textPrimary)
                        }
                    }

                    HStack(spacing: 4) {
                        ForEach(0..<8, id: \.self) { index in
                            RoundedRectangle(cornerRadius: 2, style: .continuous)
                                .fill(AppTheme.Colors.accentSecondary.opacity(0.75))
                                .frame(width: 4, height: waveHeight(for: index))
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .animation(.easeInOut(duration: 0.7).repeatForever(autoreverses: true), value: isWaveAnimating)
                    .padding(.vertical, 2)

                    HStack {
                        Text("Agent: \(viewModel.activeSession.aiAgentName)")
                            .foregroundStyle(AppTheme.Colors.textSecondary)
                        Spacer()
                        StatusBadge(
                            text: viewModel.connectionState.badgeText,
                            style: badgeStyle(for: viewModel.connectionState)
                        )
                        .accessibilityIdentifier("activeProtection.stateBadge")
                    }

                    HStack {
                        Text("Mode")
                            .foregroundStyle(AppTheme.Colors.textSecondary)
                        Spacer()
                        Text(viewModel.connectionModeLabel)
                            .foregroundStyle(AppTheme.Colors.textPrimary)
                            .font(.subheadline.weight(.semibold))
                            .accessibilityIdentifier("activeProtection.modeLabel")
                    }

                    if let callerLabel = viewModel.activeSession.callerLabel {
                        HStack {
                            Text("Caller")
                                .foregroundStyle(AppTheme.Colors.textSecondary)
                            Spacer()
                            Text(callerLabel)
                                .foregroundStyle(AppTheme.Colors.textPrimary)
                                .font(.subheadline.weight(.semibold))
                        }
                    }

                    Text(viewModel.activeSession.statusText)
                        .foregroundStyle(statusColor(for: viewModel.connectionState))
                        .font(.subheadline.weight(.semibold))

                    if viewModel.activeSession.sourceCallSessionID != nil {
                        HStack(spacing: 8) {
                            StatusBadge(text: "Linked to incoming call", style: .info)
                            if let callCategory = viewModel.activeSession.callCategory {
                                StatusBadge(
                                    text: callCategory.title,
                                    style: callCategory == .scam ? .danger : .warning
                                )
                            }
                        }
                    }
                }
            }

            AppCard(title: "Live Conversation", subtitle: "Protected-call simulation timeline") {
                VStack(spacing: 0) {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 10) {
                            if viewModel.conversationTimeline.isEmpty {
                                Text("Preparing simulated caller turns and AI replies...")
                                    .foregroundStyle(AppTheme.Colors.textSecondary)
                                    .font(.subheadline)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.vertical, 8)
                            }

                            ForEach(viewModel.conversationTimeline) { message in
                                conversationBubble(message)
                                    .accessibilityIdentifier(
                                        message.speaker == .caller
                                        ? "activeProtection.timeline.callerMessage.\(message.order)"
                                        : "activeProtection.timeline.aiMessage.\(message.order)"
                                    )
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(maxHeight: 320)
                    .animation(.easeOut(duration: 0.24), value: viewModel.conversationTimeline)
                }
                .accessibilityElement(children: .contain)
                .accessibilityIdentifier("activeProtection.timeline.container")
            }

            AppCard(title: "Detected Scam Indicators", subtitle: "Risk evidence") {
                VStack(alignment: .leading, spacing: 10) {
                    if viewModel.scamIndicators.isEmpty {
                        Text("Monitoring caller behavior...")
                            .foregroundStyle(AppTheme.Colors.textSecondary)
                            .font(.subheadline)
                    }

                    ForEach(viewModel.scamIndicators, id: \.self) { indicator in
                        HStack {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundStyle(AppTheme.Colors.danger)
                            Text(indicator)
                                .foregroundStyle(AppTheme.Colors.textPrimary)
                                .font(.subheadline.weight(.semibold))
                            Spacer()
                            Text("LIVE")
                                .font(.caption2.weight(.bold))
                                .foregroundStyle(AppTheme.Colors.danger)
                        }
                        .padding(.vertical, 8)
                        .padding(.horizontal, 10)
                        .background(AppTheme.Colors.surfaceStrong)
                        .overlay(
                            RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous)
                                .stroke(AppTheme.Colors.danger.opacity(0.35), lineWidth: 1)
                        )
                        .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous))
                        .transition(.asymmetric(insertion: .move(edge: .bottom).combined(with: .opacity), removal: .opacity))
                    }
                }
                .animation(.easeOut(duration: 0.3), value: viewModel.scamIndicators.count)
                .accessibilityIdentifier("activeProtection.indicators.section")
            }

            AppCard(title: "Extracted Entities", subtitle: "Suspicious data points") {
                VStack(alignment: .leading, spacing: 10) {
                    if viewModel.extractedEntities.isEmpty {
                        Text("Extracting entities from transcript...")
                            .foregroundStyle(AppTheme.Colors.textSecondary)
                            .font(.subheadline)
                    }

                    ForEach(viewModel.extractedEntities) { entity in
                        VStack(alignment: .leading, spacing: 8) {
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(entity.key)
                                        .foregroundStyle(AppTheme.Colors.textSecondary)
                                        .font(.caption)
                                    Text(entity.value)
                                        .foregroundStyle(AppTheme.Colors.textPrimary)
                                        .font(.subheadline.weight(.semibold))
                                }
                                Spacer()
                                StatusBadge(text: "\(entity.confidence)%", style: .info)
                            }

                            GeometryReader { geometry in
                                let normalized = min(max(Double(entity.confidence) / 100, 0), 1)
                                ZStack(alignment: .leading) {
                                    Capsule()
                                        .fill(AppTheme.Colors.surface)
                                    Capsule()
                                        .fill(confidenceColor(for: entity.confidence))
                                        .frame(width: geometry.size.width * normalized)
                                }
                            }
                            .frame(height: 6)
                        }
                        .padding(.vertical, 8)
                        .padding(.horizontal, 10)
                        .background(AppTheme.Colors.surfaceStrong)
                        .overlay(
                            RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous)
                                .stroke(AppTheme.Colors.border, lineWidth: 1)
                        )
                        .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous))
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                    }
                }
                .animation(.easeOut(duration: 0.3), value: viewModel.extractedEntities.count)
                .accessibilityIdentifier("activeProtection.entities.section")
            }

            AppCard(title: "Business Intelligence Handoff", subtitle: "Next system step") {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Connected to Fraud Intelligence Pipeline")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(AppTheme.Colors.accentSecondary)

                    ForEach(Array(viewModel.handoffPipeline.enumerated()), id: \.offset) { index, step in
                        let isCompleted = index < viewModel.handoffCompletedCount
                        let isCurrent = index == viewModel.handoffCompletedCount

                        HStack {
                            Image(systemName: isCompleted ? "checkmark.circle.fill" : (isCurrent ? "clock.badge.exclamationmark.fill" : "circle.dotted"))
                                .foregroundStyle(isCompleted ? AppTheme.Colors.success : (isCurrent ? AppTheme.Colors.warning : AppTheme.Colors.textTertiary))

                            Text(step)
                                .foregroundStyle(isCompleted ? AppTheme.Colors.textPrimary : AppTheme.Colors.textSecondary)

                            Spacer()

                            Text(isCompleted ? "Done" : (isCurrent ? "In Progress" : "Pending"))
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(isCompleted ? AppTheme.Colors.success : (isCurrent ? AppTheme.Colors.warning : AppTheme.Colors.textTertiary))
                        }
                        .padding(.vertical, 8)
                        .padding(.horizontal, 10)
                        .background(AppTheme.Colors.surfaceStrong)
                        .overlay(
                            RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous)
                                .stroke(AppTheme.Colors.border, lineWidth: 1)
                        )
                        .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous))
                        .transition(.opacity)
                    }
                }
                .animation(.easeOut(duration: 0.3), value: viewModel.handoffCompletedCount)
                .accessibilityIdentifier("activeProtection.handoff.section")
            }

            if viewModel.canRetryLiveConnection {
                SecondaryButton(title: "Retry Live Connection") {
                    viewModel.retryLiveConnection()
                }
                .accessibilityIdentifier("activeProtection.retryLiveConnection")
            }

            PrimaryButton(title: "End Session", action: onEndSession)
        }
        .onAppear {
            isPulsing = true
            isWaveAnimating = true
            viewModel.start()
        }
        .onDisappear {
            viewModel.stop()
            isWaveAnimating = false
        }
    }

    private func waveHeight(for index: Int) -> CGFloat {
        let base: CGFloat = 6
        let active: CGFloat = isWaveAnimating ? 14 : 8
        return index.isMultiple(of: 2) ? base : active
    }

    private func timeTag(for date: Date) -> String {
        let secondsAgo = max(Int(Date().timeIntervalSince(date)), 0)
        return "-\(secondsAgo)s"
    }

    private func conversationBubble(_ message: ConversationTimelineMessage) -> some View {
        let isCaller = message.speaker == .caller

        return HStack(alignment: .top, spacing: 10) {
            if isCaller {
                Image(systemName: "phone.fill")
                    .font(.caption)
                    .foregroundStyle(AppTheme.Colors.warning)
                    .frame(width: 18)
            } else {
                Image(systemName: "shield.lefthalf.filled")
                    .font(.caption)
                    .foregroundStyle(AppTheme.Colors.success)
                    .frame(width: 18)
            }

            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .center) {
                    Text(message.speaker.displayName)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(isCaller ? AppTheme.Colors.warning : AppTheme.Colors.success)

                    Spacer()

                    Text(timeTag(for: message.receivedAt))
                        .font(.caption2.monospacedDigit())
                        .foregroundStyle(AppTheme.Colors.textTertiary)
                }

                Text(message.text)
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.Colors.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)

                if message.status == .partial {
                    Text("Streaming…")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(AppTheme.Colors.accentSecondary)
                } else if message.status == .corrected {
                    Text("Corrected")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(AppTheme.Colors.warning)
                } else if message.status == .fallback {
                    Text("Fallback")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(AppTheme.Colors.warning)
                }
            }
            .padding(.vertical, 8)
            .padding(.horizontal, 10)
            .background(
                isCaller
                ? AppTheme.Colors.warning.opacity(0.12)
                : AppTheme.Colors.success.opacity(0.12)
            )
            .overlay(
                RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous)
                    .stroke(
                        isCaller
                        ? AppTheme.Colors.warning.opacity(0.35)
                        : AppTheme.Colors.success.opacity(0.35),
                        lineWidth: 1
                    )
            )
            .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.input, style: .continuous))
        }
    }

    private func confidenceColor(for confidence: Int) -> Color {
        if confidence >= 85 {
            return AppTheme.Colors.danger
        }
        if confidence >= 65 {
            return AppTheme.Colors.warning
        }
        return AppTheme.Colors.accentSecondary
    }

    private func badgeStyle(for state: ProtectionConnectionState) -> StatusBadgeStyle {
        switch state {
        case .prepared:
            return .info
        case .connecting:
            return .warning
        case .live:
            return .success
        case .playingDemoAudio:
            return .warning
        case .receivingAgentEvents:
            return .success
        case .degraded:
            return .danger
        }
    }

    private func statusColor(for state: ProtectionConnectionState) -> Color {
        switch state {
        case .prepared:
            return AppTheme.Colors.accentSecondary
        case .connecting:
            return AppTheme.Colors.warning
        case .live:
            return AppTheme.Colors.success
        case .playingDemoAudio:
            return AppTheme.Colors.warning
        case .receivingAgentEvents:
            return AppTheme.Colors.success
        case .degraded:
            return AppTheme.Colors.warning
        }
    }
}
