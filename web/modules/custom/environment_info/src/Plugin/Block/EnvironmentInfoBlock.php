<?php

declare(strict_types=1);

namespace Drupal\environment_info\Plugin\Block;

use Drupal\environment_info\BuildInfo;
use Drupal\Core\Block\Attribute\Block;
use Drupal\Core\Block\BlockBase;
use Drupal\Core\Plugin\ContainerFactoryPluginInterface;
use Drupal\Core\StringTranslation\TranslatableMarkup;
use Symfony\Component\DependencyInjection\ContainerInterface;

#[Block(
  id: 'environment_info',
  admin_label: new TranslatableMarkup('Environment info'),
  category: new TranslatableMarkup('Custom'),
)]
final class EnvironmentInfoBlock extends BlockBase implements ContainerFactoryPluginInterface {

  public function __construct(
    array $configuration,
    string $plugin_id,
    array $plugin_definition,
    private readonly BuildInfo $buildInfo,
  ) {
    parent::__construct($configuration, $plugin_id, $plugin_definition);
  }

  public static function create(ContainerInterface $container, array $configuration, $plugin_id, $plugin_definition): static {
    return new static(
      $configuration,
      $plugin_id,
      $plugin_definition,
      $container->get('environment_info.build_info'),
    );
  }

  public function defaultConfiguration(): array {
    return [
      'label_display' => '0',
    ];
  }

  public function build(): array {
    $info = $this->buildInfo->get();

    return [
      '#type' => 'component',
      '#component' => 'environment_info:environment-info',
      '#props' => [
        'environment' => $info['environment'],
        'version' => $info['version'],
        'branch' => $info['branch'],
      ],
      '#cache' => [
        'max-age' => $this->getCacheMaxAge(),
      ],
    ];
  }

  public function getCacheMaxAge(): int {
    return 300;
  }

}
