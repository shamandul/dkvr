<?php

declare(strict_types=1);

namespace Drupal\Tests\environment_info\Unit;

use Drupal\environment_info\BuildInfo;
use Drupal\Tests\UnitTestCase;
use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\Attributes\Group;

#[CoversClass(BuildInfo::class)]
#[Group('environment_info')]
final class BuildInfoTest extends UnitTestCase {

  private const ENV_VARS = ['APP_ENV', 'ENVIRONMENT', 'IS_DDEV_PROJECT', 'GIT_VERSION', 'GIT_BRANCH'];

  private string $appRoot;

  protected function setUp(): void {
    parent::setUp();
    $this->appRoot = sys_get_temp_dir() . '/environment-info-build-info-test';
    $this->clearEnvironment();
  }

  protected function tearDown(): void {
    $this->clearEnvironment();
    parent::tearDown();
  }

  #[DataProvider('environmentProvider')]
  public function testResolveEnvironment(array $environment, string $expected): void {
    foreach ($environment as $name => $value) {
      putenv($name . '=' . $value);
    }

    $this->assertSame($expected, $this->buildInfo()->get()['environment']);
  }

  public static function environmentProvider(): array {
    return [
      'APP_ENV=dev' => [['APP_ENV' => 'dev'], 'dev'],
      'APP_ENV se normaliza a minúsculas' => [['APP_ENV' => 'INT'], 'int'],
      'APP_ENV pre' => [['APP_ENV' => 'pre'], 'pre'],
      'APP_ENV pro' => [['APP_ENV' => 'pro'], 'pro'],
      'APP_ENV tiene prioridad sobre ENVIRONMENT' => [
        ['APP_ENV' => 'pre', 'ENVIRONMENT' => 'pro'],
        'pre',
      ],
      'solo ENVIRONMENT' => [['ENVIRONMENT' => 'int'], 'int'],
      'IS_DDEV_PROJECT sin APP_ENV es unknown' => [['IS_DDEV_PROJECT' => 'true'], 'unknown'],
      'APP_ENV vacío es unknown' => [['APP_ENV' => '   '], 'unknown'],
      'sin variables es unknown' => [[], 'unknown'],
    ];
  }

  public function testGetReturnsVersionAndBranchFromEnvironment(): void {
    putenv('APP_ENV=dev');
    putenv('GIT_VERSION=v1.2.3');
    putenv('GIT_BRANCH=feature/multi-env');

    $this->assertSame(
      [
        'environment' => 'dev',
        'version' => 'v1.2.3',
        'branch' => 'feature/multi-env',
      ],
      $this->buildInfo()->get(),
    );
  }

  private function buildInfo(): BuildInfo {
    return new BuildInfo($this->appRoot);
  }

  private function clearEnvironment(): void {
    foreach (self::ENV_VARS as $name) {
      putenv($name);
    }
  }

}
