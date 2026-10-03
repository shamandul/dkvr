<?php

declare(strict_types=1);

namespace Drupal\environment_info;

use Symfony\Component\Process\Exception\RuntimeException;
use Symfony\Component\Process\Process;

final class BuildInfo {

  private const ENVIRONMENT_VARIABLES = ['APP_ENV', 'ENVIRONMENT'];

  private const GIT_TIMEOUT = 5.0;

  private ?array $info = NULL;

  public function __construct(private readonly string $appRoot) {}

  public function get(): array {
    return $this->info ??= [
      'environment' => $this->resolveEnvironment(),
      'version' => $this->resolveVersion(),
      'branch' => $this->resolveBranch(),
    ];
  }

  private function resolveEnvironment(): string {
    foreach (self::ENVIRONMENT_VARIABLES as $name) {
      $value = $this->envVariable($name);
      if ($value !== NULL) {
        return mb_strtolower($value);
      }
    }
    return getenv('IS_DDEV_PROJECT') ? 'dev' : 'prod';
  }

  private function resolveVersion(): string {
    return $this->envVariable('GIT_VERSION')
      ?? $this->git('describe', '--tags', '--always')
      ?? '';
  }

  private function resolveBranch(): string {
    $branch = $this->envVariable('GIT_BRANCH')
      ?? $this->git('rev-parse', '--abbrev-ref', 'HEAD');
    if ($branch === NULL) {
      return '';
    }
    if ($branch === 'HEAD') {
      return $this->git('rev-parse', '--short', 'HEAD') ?? '';
    }
    return $branch;
  }

  private function envVariable(string $name): ?string {
    $value = getenv($name);
    if (!is_string($value) || trim($value) === '') {
      return NULL;
    }
    return trim($value);
  }

  private function git(string ...$arguments): ?string {
    $cwd = $this->gitRoot();
    if ($cwd === NULL) {
      return NULL;
    }
    $process = new Process(['git', ...$arguments], $cwd, timeout: self::GIT_TIMEOUT);
    try {
      $process->mustRun();
    }
    catch (RuntimeException) {
      return NULL;
    }
    $output = trim($process->getOutput());
    return $output === '' ? NULL : $output;
  }

  private function gitRoot(): ?string {
    foreach ([$this->appRoot, dirname($this->appRoot)] as $directory) {
      $gitPath = $directory . DIRECTORY_SEPARATOR . '.git';
      if (is_dir($gitPath)) {
        return $directory;
      }
      if (is_file($gitPath) && $this->isResolvableGitLink($gitPath)) {
        return $directory;
      }
    }
    return NULL;
  }

  private function isResolvableGitLink(string $path): bool {
    $contents = file_get_contents($path);
    if (!is_string($contents) || !preg_match('/^gitdir:\s*(.+?)\s*$/m', $contents, $matches)) {
      return FALSE;
    }
    $gitDirectory = $matches[1];
    if (!str_starts_with($gitDirectory, DIRECTORY_SEPARATOR)) {
      $gitDirectory = dirname($path) . DIRECTORY_SEPARATOR . $gitDirectory;
    }
    return is_dir($gitDirectory);
  }

}
