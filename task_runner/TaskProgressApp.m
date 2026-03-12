#import <Cocoa/Cocoa.h>

static NSString *Localized(NSString *zh, NSString *en) {
    NSArray<NSString *> *langs = [NSLocale preferredLanguages];
    NSString *first = langs.count > 0 ? langs[0].lowercaseString : @"";
    return [first hasPrefix:@"zh"] ? zh : en;
}

static NSString *SanitizeOutput(NSString *value) {
    if (value.length == 0) {
        return @"";
    }
    NSString *normalized = [value stringByReplacingOccurrencesOfString:@"\r" withString:@"\n"];
    NSError *error = nil;
    NSRegularExpression *regex = [NSRegularExpression regularExpressionWithPattern:@"\\x1B\\[[0-9;?]*[ -/]*[@-~]"
                                                                           options:0
                                                                             error:&error];
    if (regex == nil || error != nil) {
        return normalized;
    }
    return [regex stringByReplacingMatchesInString:normalized
                                           options:0
                                             range:NSMakeRange(0, normalized.length)
                                      withTemplate:@""];
}

@interface TaskRunnerConfig : NSObject
@property(nonatomic, copy) NSString *mode;
@property(nonatomic, copy) NSString *appDisplayName;
@property(nonatomic, copy) NSString *scriptRelativePath;
@property(nonatomic, assign) BOOL confirmRequired;
@property(nonatomic, assign) BOOL showSuccessOpenButton;
@property(nonatomic, assign) BOOL showDesktopShortcutButton;
@end

@implementation TaskRunnerConfig
@end

@interface TaskProgressApp : NSObject <NSApplicationDelegate, NSWindowDelegate>
@property(nonatomic, strong) TaskRunnerConfig *config;
@property(nonatomic, strong) NSWindow *window;
@property(nonatomic, strong) NSImageView *iconView;
@property(nonatomic, strong) NSTextField *titleLabel;
@property(nonatomic, strong) NSTextField *statusLabel;
@property(nonatomic, strong) NSProgressIndicator *progressBar;
@property(nonatomic, strong) NSScrollView *logScrollView;
@property(nonatomic, strong) NSTextView *logTextView;
@property(nonatomic, strong) NSButton *closeButton;
@property(nonatomic, strong) NSButton *actionButton;
@property(nonatomic, strong) NSButton *secondaryActionButton;
@property(nonatomic, strong) NSTask *task;
@property(nonatomic, strong) NSPipe *pipe;
@property(nonatomic, strong) NSMutableString *partialLine;
@property(nonatomic, strong) NSMutableArray<NSDictionary *> *pendingWarnings;
@property(nonatomic, assign) BOOL sawProgress;
@property(nonatomic, assign) BOOL finished;
@end

@implementation TaskProgressApp

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    (void)notification;
    [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];

    self.config = [self loadConfig];
    if (self.config == nil) {
        [self showFatalAlert:Localized(@"配置读取失败。", @"Failed to load task runner config.")];
        [NSApp terminate:nil];
        return;
    }

    self.partialLine = [NSMutableString string];
    self.pendingWarnings = [NSMutableArray array];
    [self buildWindow];
    [NSApp activateIgnoringOtherApps:YES];

    if (self.config.confirmRequired && ![self confirmStart]) {
        [NSApp terminate:nil];
        return;
    }

    [self startTask];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    (void)sender;
    return YES;
}

- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    (void)sender;
    if (self.finished) {
        return NSTerminateNow;
    }
    NSBeep();
    self.statusLabel.stringValue = Localized(@"任务仍在进行中，请等待完成。", @"Task is still running. Please wait for completion.");
    return NSTerminateCancel;
}

- (BOOL)windowShouldClose:(id)sender {
    (void)sender;
    if (self.finished) {
        return YES;
    }
    NSBeep();
    self.statusLabel.stringValue = Localized(@"任务仍在进行中，请等待完成。", @"Task is still running. Please wait for completion.");
    return NO;
}

- (TaskRunnerConfig *)loadConfig {
    NSString *path = [[NSBundle mainBundle] pathForResource:@"TaskRunnerConfig" ofType:@"plist"];
    if (path == nil) {
        return nil;
    }
    NSDictionary *raw = [NSDictionary dictionaryWithContentsOfFile:path];
    if (![raw isKindOfClass:[NSDictionary class]]) {
        return nil;
    }
    TaskRunnerConfig *cfg = [TaskRunnerConfig new];
    cfg.mode = [raw[@"Mode"] isKindOfClass:[NSString class]] ? raw[@"Mode"] : @"task";
    cfg.appDisplayName = [raw[@"AppDisplayName"] isKindOfClass:[NSString class]] ? raw[@"AppDisplayName"] : @"FunASR Dictation";
    cfg.scriptRelativePath = [raw[@"ScriptRelativePath"] isKindOfClass:[NSString class]] ? raw[@"ScriptRelativePath"] : @"run_task.sh";
    cfg.confirmRequired = [raw[@"ConfirmRequired"] respondsToSelector:@selector(boolValue)] ? [raw[@"ConfirmRequired"] boolValue] : NO;
    cfg.showSuccessOpenButton = [raw[@"ShowSuccessOpenButton"] respondsToSelector:@selector(boolValue)] ? [raw[@"ShowSuccessOpenButton"] boolValue] : NO;
    cfg.showDesktopShortcutButton = [raw[@"ShowDesktopShortcutButton"] respondsToSelector:@selector(boolValue)] ? [raw[@"ShowDesktopShortcutButton"] boolValue] : NO;
    return cfg;
}

- (NSString *)windowTitle {
    if ([self.config.mode isEqualToString:@"uninstall"]) {
        return Localized(
            [NSString stringWithFormat:@"卸载 %@", self.config.appDisplayName],
            [NSString stringWithFormat:@"Uninstall %@", self.config.appDisplayName]
        );
    }
    return Localized(
        [NSString stringWithFormat:@"安装 %@", self.config.appDisplayName],
        [NSString stringWithFormat:@"Install %@", self.config.appDisplayName]
    );
}

- (NSString *)initialStatus {
    return Localized(@"准备中…", @"Preparing...");
}

- (NSString *)successStatus {
    if ([self.config.mode isEqualToString:@"uninstall"]) {
        return Localized(@"卸载已完成。", @"Uninstall completed.");
    }
    return Localized(@"安装已完成。", @"Installation completed.");
}

- (NSString *)failureStatus {
    if ([self.config.mode isEqualToString:@"uninstall"]) {
        return Localized(@"卸载失败。", @"Uninstall failed.");
    }
    return Localized(@"安装失败。", @"Installation failed.");
}

- (void)buildWindow {
    NSRect frame = NSMakeRect(0, 0, 720, 560);
    self.window = [[NSWindow alloc] initWithContentRect:frame
                                              styleMask:(NSWindowStyleMaskTitled |
                                                         NSWindowStyleMaskClosable |
                                                         NSWindowStyleMaskMiniaturizable)
                                                backing:NSBackingStoreBuffered
                                                  defer:NO];
    [self.window setTitle:[self windowTitle]];
    [self.window center];
    self.window.delegate = self;

    NSView *content = self.window.contentView;

    self.iconView = [[NSImageView alloc] initWithFrame:NSMakeRect(40, 468, 72, 72)];
    self.iconView.image = NSApp.applicationIconImage;
    self.iconView.imageScaling = NSImageScaleProportionallyUpOrDown;
    [content addSubview:self.iconView];

    self.titleLabel = [self labelWithFrame:NSMakeRect(132, 492, 540, 32)
                                      text:[self windowTitle]
                                      font:[NSFont boldSystemFontOfSize:26]];
    [content addSubview:self.titleLabel];

    self.statusLabel = [self wrappingLabelWithFrame:NSMakeRect(132, 440, 540, 44)
                                               text:[self initialStatus]
                                               font:[NSFont systemFontOfSize:15 weight:NSFontWeightMedium]];
    [content addSubview:self.statusLabel];

    self.progressBar = [[NSProgressIndicator alloc] initWithFrame:NSMakeRect(40, 414, 632, 20)];
    self.progressBar.indeterminate = YES;
    self.progressBar.style = NSProgressIndicatorStyleBar;
    self.progressBar.displayedWhenStopped = YES;
    [self.progressBar startAnimation:nil];
    [content addSubview:self.progressBar];

    NSRect logFrame = NSMakeRect(40, 88, 632, 308);
    self.logTextView = [[NSTextView alloc] initWithFrame:NSMakeRect(0, 0, logFrame.size.width, logFrame.size.height)];
    self.logTextView.editable = NO;
    self.logTextView.selectable = YES;
    self.logTextView.font = [NSFont fontWithName:@"Menlo" size:11] ?: [NSFont monospacedSystemFontOfSize:11 weight:NSFontWeightRegular];
    self.logTextView.textColor = NSColor.labelColor;
    self.logTextView.backgroundColor = NSColor.textBackgroundColor;

    self.logScrollView = [[NSScrollView alloc] initWithFrame:logFrame];
    self.logScrollView.hasVerticalScroller = YES;
    self.logScrollView.hasHorizontalScroller = NO;
    self.logScrollView.documentView = self.logTextView;
    [content addSubview:self.logScrollView];

    self.closeButton = [[NSButton alloc] initWithFrame:NSMakeRect(552, 28, 120, 36)];
    self.closeButton.bezelStyle = NSBezelStyleRounded;
    self.closeButton.title = Localized(@"关闭", @"Close");
    self.closeButton.enabled = NO;
    self.closeButton.target = self;
    self.closeButton.action = @selector(onClose:);
    [content addSubview:self.closeButton];

    self.actionButton = [[NSButton alloc] initWithFrame:NSMakeRect(404, 28, 136, 36)];
    self.actionButton.bezelStyle = NSBezelStyleRounded;
    self.actionButton.title = Localized(@"打开应用", @"Open App");
    self.actionButton.hidden = YES;
    self.actionButton.enabled = NO;
    self.actionButton.target = self;
    self.actionButton.action = @selector(onPrimaryAction:);
    [content addSubview:self.actionButton];

    self.secondaryActionButton = [[NSButton alloc] initWithFrame:NSMakeRect(216, 28, 176, 36)];
    self.secondaryActionButton.bezelStyle = NSBezelStyleRounded;
    self.secondaryActionButton.title = Localized(@"创建桌面快捷方式", @"Create Desktop Shortcut");
    self.secondaryActionButton.hidden = YES;
    self.secondaryActionButton.enabled = NO;
    self.secondaryActionButton.target = self;
    self.secondaryActionButton.action = @selector(onSecondaryAction:);
    [content addSubview:self.secondaryActionButton];

    [self.window makeKeyAndOrderFront:nil];
}

- (NSTextField *)labelWithFrame:(NSRect)frame text:(NSString *)text font:(NSFont *)font {
    NSTextField *label = [[NSTextField alloc] initWithFrame:frame];
    label.stringValue = text ?: @"";
    label.font = font;
    label.bezeled = NO;
    label.drawsBackground = NO;
    label.editable = NO;
    label.selectable = NO;
    label.lineBreakMode = NSLineBreakByTruncatingTail;
    return label;
}

- (NSTextField *)wrappingLabelWithFrame:(NSRect)frame text:(NSString *)text font:(NSFont *)font {
    NSTextField *label = [self labelWithFrame:frame text:text font:font];
    label.lineBreakMode = NSLineBreakByWordWrapping;
    label.usesSingleLineMode = NO;
    NSTextFieldCell *cell = (NSTextFieldCell *)label.cell;
    cell.wraps = YES;
    return label;
}

- (BOOL)confirmStart {
    NSAlert *alert = [[NSAlert alloc] init];
    alert.alertStyle = NSAlertStyleWarning;
    alert.messageText = Localized(@"确认卸载", @"Confirm Uninstall");
    alert.informativeText = Localized(
        [NSString stringWithFormat:@"这将移除 %@、启动器、Python runtime、模型缓存和本地设置。", self.config.appDisplayName],
        [NSString stringWithFormat:@"This will remove %@, its launcher, Python runtime, model cache, and local settings.", self.config.appDisplayName]
    );
    [alert addButtonWithTitle:Localized(@"卸载", @"Uninstall")];
    [alert addButtonWithTitle:Localized(@"取消", @"Cancel")];
    return [alert runModal] == NSAlertFirstButtonReturn;
}

- (void)startTask {
    NSString *scriptPath = [[[NSBundle mainBundle] resourcePath] stringByAppendingPathComponent:self.config.scriptRelativePath];
    if (![[NSFileManager defaultManager] isReadableFileAtPath:scriptPath]) {
        [self appendLog:[NSString stringWithFormat:@"[ERROR] %@\n",
                         Localized([NSString stringWithFormat:@"缺少任务脚本：%@", scriptPath],
                                   [NSString stringWithFormat:@"Missing task script: %@", scriptPath])]];
        [self finishWithStatus:1];
        return;
    }

    self.task = [[NSTask alloc] init];
    self.task.executableURL = [NSURL fileURLWithPath:@"/bin/bash"];
    self.task.arguments = @[scriptPath];

    NSMutableDictionary<NSString *, NSString *> *env = [NSMutableDictionary dictionaryWithDictionary:NSProcessInfo.processInfo.environment];
    env[@"FUNASR_UI_MODE"] = @"1";
    self.task.environment = env;

    self.pipe = [NSPipe pipe];
    self.task.standardOutput = self.pipe;
    self.task.standardError = self.pipe;

    __weak typeof(self) weakSelf = self;
    self.pipe.fileHandleForReading.readabilityHandler = ^(NSFileHandle *handle) {
        NSData *data = [handle availableData];
        if (data.length == 0) {
            return;
        }
        dispatch_async(dispatch_get_main_queue(), ^{
            [weakSelf consumeOutputData:data];
        });
    };
    self.task.terminationHandler = ^(NSTask *task) {
        dispatch_async(dispatch_get_main_queue(), ^{
            weakSelf.pipe.fileHandleForReading.readabilityHandler = nil;
            [weakSelf flushPartialLine];
            [weakSelf finishWithStatus:task.terminationStatus];
        });
    };

    NSError *error = nil;
    if (![self.task launchAndReturnError:&error]) {
        NSString *fallback = Localized(@"无法启动任务。", @"Failed to launch task.");
        [self appendLog:[NSString stringWithFormat:@"[ERROR] %@\n", error.localizedDescription ?: fallback]];
        [self finishWithStatus:1];
        return;
    }
}

- (void)consumeOutputData:(NSData *)data {
    NSString *chunk = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    if (chunk.length == 0) {
        chunk = [[NSString alloc] initWithData:data encoding:NSISOLatin1StringEncoding] ?: @"";
    }
    [self.partialLine appendString:SanitizeOutput(chunk ?: @"")];

    while (YES) {
        NSRange newlineRange = [self.partialLine rangeOfString:@"\n"];
        if (newlineRange.location == NSNotFound) {
            break;
        }
        NSString *line = [self.partialLine substringToIndex:newlineRange.location];
        [self.partialLine deleteCharactersInRange:NSMakeRange(0, newlineRange.location + 1)];
        [self handleLine:line];
    }
}

- (void)flushPartialLine {
    if (self.partialLine.length > 0) {
        [self handleLine:self.partialLine.copy];
        [self.partialLine setString:@""];
    }
}

- (void)handleLine:(NSString *)line {
    if (line == nil) {
        return;
    }
    [self appendLog:[line stringByAppendingString:@"\n"]];

    if ([line hasPrefix:@"[Progress] "]) {
        NSString *rest = [line substringFromIndex:11];
        NSScanner *scanner = [NSScanner scannerWithString:rest];
        NSInteger percent = 0;
        if ([scanner scanInteger:&percent]) {
            NSString *message = @"";
            if (scanner.scanLocation < rest.length) {
                message = [[rest substringFromIndex:scanner.scanLocation] stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceCharacterSet];
            }
            [self updateProgress:percent message:message];
            return;
        }
    }

    if ([line hasPrefix:@"[Step] "]) {
        self.statusLabel.stringValue = [line substringFromIndex:7];
        return;
    }
    if ([line hasPrefix:@"[ERROR] "]) {
        self.statusLabel.stringValue = [line substringFromIndex:8];
        return;
    }
    if ([line hasPrefix:@"[WARN_CODE] "]) {
        [self handleWarningCode:[line substringFromIndex:12]];
        return;
    }
    if ([line hasPrefix:@"[WARN] "]) {
        self.statusLabel.stringValue = [line substringFromIndex:7];
        return;
    }
    if ([line hasPrefix:@"[Done]"]) {
        [self updateProgress:100 message:[self successStatus]];
    }
}

- (void)handleWarningCode:(NSString *)payload {
    NSArray<NSString *> *parts = [payload componentsSeparatedByString:@"|"];
    if (parts.count == 0) {
        return;
    }
    NSString *code = parts[0];
    NSString *argument = parts.count > 1 ? parts[1] : @"";
    if ([code isEqualToString:@"DESKTOP_SHORTCUT_MANUAL_REMOVE"]) {
        [self.pendingWarnings addObject:@{
            @"code": code,
            @"path": argument ?: @""
        }];
        self.statusLabel.stringValue = Localized(
            @"卸载已完成，但桌面快捷方式需要你手动删除。",
            @"Uninstall completed, but the Desktop shortcut needs to be removed manually."
        );
    }
}

- (void)updateProgress:(NSInteger)percent message:(NSString *)message {
    NSInteger clamped = MAX(0, MIN(100, percent));
    if (!self.sawProgress) {
        self.sawProgress = YES;
        self.progressBar.indeterminate = NO;
        self.progressBar.minValue = 0;
        self.progressBar.maxValue = 100;
        [self.progressBar stopAnimation:nil];
    }
    self.progressBar.doubleValue = clamped;
    if (message.length > 0) {
        self.statusLabel.stringValue = message;
    }
}

- (void)appendLog:(NSString *)text {
    if (text.length == 0) {
        return;
    }
    NSAttributedString *attr = [[NSAttributedString alloc] initWithString:text];
    [self.logTextView.textStorage appendAttributedString:attr];
    [self.logTextView scrollRangeToVisible:NSMakeRange(self.logTextView.string.length, 0)];
}

- (void)finishWithStatus:(int)status {
    if (self.finished) {
        return;
    }
    self.finished = YES;
    self.closeButton.enabled = YES;
    if (!self.sawProgress) {
        self.progressBar.indeterminate = NO;
        self.progressBar.minValue = 0;
        self.progressBar.maxValue = 100;
        [self.progressBar stopAnimation:nil];
    }
    if (status == 0) {
        self.progressBar.doubleValue = 100;
        self.statusLabel.stringValue = [self successStatus];
        [self appendLog:[NSString stringWithFormat:@"[Done] %@\n", [self successStatus]]];
        if (self.config.showSuccessOpenButton && [self.config.mode isEqualToString:@"install"]) {
            self.actionButton.hidden = NO;
            self.actionButton.enabled = YES;
            self.closeButton.frame = NSMakeRect(552, 28, 120, 36);
        }
        if (self.config.showDesktopShortcutButton && [self.config.mode isEqualToString:@"install"]) {
            self.secondaryActionButton.hidden = NO;
            self.secondaryActionButton.enabled = YES;
            self.statusLabel.stringValue = Localized(
                @"安装已完成。如需创建桌面快捷方式，请点击下方按钮。",
                @"Installation completed. To create a Desktop shortcut, click the button below."
            );
        }
        [self presentPendingWarningsIfNeeded];
    } else {
        if (self.progressBar.doubleValue < 100) {
            self.progressBar.doubleValue = MAX(self.progressBar.doubleValue, 1);
        }
        self.statusLabel.stringValue = [self failureStatus];
        [self appendLog:[NSString stringWithFormat:@"[ERROR] %@\n", [self failureStatus]]];
    }
}

- (void)presentPendingWarningsIfNeeded {
    if (self.pendingWarnings.count == 0) {
        return;
    }
    for (NSDictionary<NSString *, NSString *> *warning in self.pendingWarnings) {
        NSString *code = warning[@"code"] ?: @"";
        if ([code isEqualToString:@"DESKTOP_SHORTCUT_MANUAL_REMOVE"]) {
            NSString *path = warning[@"path"] ?: @"";
            NSString *message = Localized(
                [NSString stringWithFormat:@"卸载已经完成，但桌面快捷方式无法自动删除。\n\n请手动从桌面删除以下快捷方式：\n%@",
                 path.length > 0 ? path : @"~/Desktop/FunASR Dictation.app"],
                [NSString stringWithFormat:@"Uninstall completed, but the Desktop shortcut could not be removed automatically.\n\nPlease delete this shortcut manually from Desktop:\n%@",
                 path.length > 0 ? path : @"~/Desktop/FunASR Dictation.app"]
            );
            NSAlert *alert = [[NSAlert alloc] init];
            alert.alertStyle = NSAlertStyleWarning;
            alert.messageText = Localized(@"请手动删除桌面快捷方式", @"Manual Desktop Shortcut Removal Required");
            alert.informativeText = message;
            [alert addButtonWithTitle:Localized(@"我知道了", @"OK")];
            [alert runModal];
        }
    }
}

- (void)showInfoAlertWithTitle:(NSString *)title message:(NSString *)message {
    NSAlert *alert = [[NSAlert alloc] init];
    alert.alertStyle = NSAlertStyleInformational;
    alert.messageText = title ?: self.config.appDisplayName ?: @"FunASR Dictation";
    alert.informativeText = message ?: @"";
    [alert addButtonWithTitle:Localized(@"关闭", @"Close")];
    [alert runModal];
}

- (void)showFatalAlert:(NSString *)message {
    NSAlert *alert = [[NSAlert alloc] init];
    alert.alertStyle = NSAlertStyleCritical;
    alert.messageText = [self windowTitle] ?: @"FunASR Dictation";
    alert.informativeText = message ?: @"";
    [alert addButtonWithTitle:Localized(@"关闭", @"Close")];
    [alert runModal];
}

- (void)onClose:(id)sender {
    (void)sender;
    [NSApp terminate:nil];
}

- (void)onPrimaryAction:(id)sender {
    (void)sender;
    NSString *appPath = [NSString stringWithFormat:@"%@/Applications/%@.app", NSHomeDirectory(), self.config.appDisplayName ?: @"FunASR Dictation"];
    NSString *quotedPath = [appPath stringByReplacingOccurrencesOfString:@"\"" withString:@"\\\""];
    NSString *command = [NSString stringWithFormat:@"(sleep 0.4; open \"%@\") >/dev/null 2>&1 &", quotedPath];

    NSTask *openTask = [[NSTask alloc] init];
    openTask.executableURL = [NSURL fileURLWithPath:@"/bin/bash"];
    openTask.arguments = @[@"-lc", command];
    @try {
        [openTask launchAndReturnError:nil];
    } @catch (__unused NSException *exc) {
    }
    [NSApp terminate:nil];
}

- (void)onSecondaryAction:(id)sender {
    (void)sender;
    NSString *scriptPath = [NSString stringWithFormat:@"%@/Library/Application Support/FunASRDictation/app/create_desktop_shortcut.sh", NSHomeDirectory()];
    if (![[NSFileManager defaultManager] isReadableFileAtPath:scriptPath]) {
        [self showFatalAlert:Localized(@"找不到创建桌面快捷方式所需的脚本。", @"Could not find the script needed to create the Desktop shortcut.")];
        return;
    }

    NSTask *task = [[NSTask alloc] init];
    task.executableURL = [NSURL fileURLWithPath:@"/bin/bash"];
    task.arguments = @[scriptPath];
    task.environment = @{ @"HOME": NSHomeDirectory() };

    NSPipe *pipe = [NSPipe pipe];
    task.standardOutput = pipe;
    task.standardError = pipe;

    NSError *error = nil;
    if (![task launchAndReturnError:&error]) {
        [self showFatalAlert:error.localizedDescription ?: Localized(@"无法创建桌面快捷方式。", @"Could not create the Desktop shortcut.")];
        return;
    }
    [task waitUntilExit];

    NSData *outputData = [[pipe fileHandleForReading] readDataToEndOfFile];
    NSString *output = [[NSString alloc] initWithData:outputData encoding:NSUTF8StringEncoding];
    if (output.length == 0) {
        output = [[NSString alloc] initWithData:outputData encoding:NSISOLatin1StringEncoding] ?: @"";
    }
    NSString *sanitized = SanitizeOutput(output ?: @"");
    if (sanitized.length > 0) {
        [self appendLog:sanitized];
        if (![sanitized hasSuffix:@"\n"]) {
            [self appendLog:@"\n"];
        }
    }

    if (task.terminationStatus == 0) {
        self.secondaryActionButton.enabled = NO;
        self.secondaryActionButton.title = Localized(@"桌面快捷方式已创建", @"Desktop Shortcut Created");
        self.statusLabel.stringValue = Localized(
            @"桌面快捷方式已创建。卸载时如未自动删除，请手动从桌面移除。",
            @"Desktop shortcut created. If uninstall cannot remove it automatically, delete it manually from Desktop."
        );
        [self showInfoAlertWithTitle:Localized(@"桌面快捷方式已创建", @"Desktop Shortcut Created")
                             message:Localized(@"已在桌面创建快捷方式。注意：卸载时如果 macOS 阻止自动删除，你需要手动从桌面删除该快捷方式。", @"A Desktop shortcut was created. Note: if macOS blocks automatic removal during uninstall, you will need to delete the shortcut manually from Desktop.")];
        return;
    }

    [self showFatalAlert:Localized(@"创建桌面快捷方式失败。你仍然可以从 Applications 中启动应用。", @"Failed to create the Desktop shortcut. You can still launch the app from Applications.")];
}

@end

int main(int argc, const char *argv[]) {
    (void)argc;
    (void)argv;
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        TaskProgressApp *delegate = [TaskProgressApp new];
        app.delegate = delegate;
        [app run];
    }
    return 0;
}
