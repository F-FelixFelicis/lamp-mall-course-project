-- 灯具商城 v0.1 数据库结构
-- Target: MySQL 8.0+
-- Charset: utf8mb4

CREATE DATABASE IF NOT EXISTS lamp_mall
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE lamp_mall;

CREATE TABLE users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(64) NULL,
  phone VARCHAR(20) NULL,
  password_hash VARCHAR(255) NOT NULL,
  display_name VARCHAR(80) NOT NULL,
  avatar_url VARCHAR(500) NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
  last_login_at DATETIME(3) NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted_at DATETIME(3) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_username (username),
  UNIQUE KEY uk_users_phone (phone),
  KEY idx_users_status (status),
  CONSTRAINT ck_users_identity CHECK (username IS NOT NULL OR phone IS NOT NULL)
) ENGINE=InnoDB COMMENT='用户账号';

CREATE TABLE roles (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  code VARCHAR(40) NOT NULL,
  name VARCHAR(80) NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_roles_code (code)
) ENGINE=InnoDB COMMENT='角色';

CREATE TABLE user_roles (
  user_id BIGINT UNSIGNED NOT NULL,
  role_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (user_id, role_id),
  CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES roles (id)
) ENGINE=InnoDB COMMENT='用户角色关联';

CREATE TABLE uploaded_files (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  owner_user_id BIGINT UNSIGNED NOT NULL,
  storage_key VARCHAR(500) NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  content_type VARCHAR(120) NOT NULL,
  size_bytes BIGINT UNSIGNED NOT NULL,
  sha256 CHAR(64) NOT NULL,
  access_level VARCHAR(20) NOT NULL DEFAULT 'PRIVATE',
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  deleted_at DATETIME(3) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_uploaded_files_storage_key (storage_key),
  KEY idx_uploaded_files_owner (owner_user_id, created_at),
  CONSTRAINT fk_uploaded_files_owner FOREIGN KEY (owner_user_id) REFERENCES users (id)
) ENGINE=InnoDB COMMENT='受控上传文件';

CREATE TABLE merchant_profiles (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  shop_name VARCHAR(120) NOT NULL,
  legal_name VARCHAR(80) NOT NULL,
  contact_phone VARCHAR(20) NOT NULL,
  address VARCHAR(255) NOT NULL,
  business_license_file_id BIGINT UNSIGNED NOT NULL,
  certification_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted_at DATETIME(3) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_merchant_profiles_user (user_id),
  KEY idx_merchant_profiles_status (certification_status),
  CONSTRAINT fk_merchant_profiles_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_merchant_profiles_license FOREIGN KEY (business_license_file_id) REFERENCES uploaded_files (id)
) ENGINE=InnoDB COMMENT='商家资料';

CREATE TABLE merchant_audits (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id BIGINT UNSIGNED NOT NULL,
  result VARCHAR(20) NOT NULL,
  reason VARCHAR(500) NULL,
  auditor_user_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_merchant_audits_merchant (merchant_id, created_at),
  CONSTRAINT fk_merchant_audits_merchant FOREIGN KEY (merchant_id) REFERENCES merchant_profiles (id),
  CONSTRAINT fk_merchant_audits_auditor FOREIGN KEY (auditor_user_id) REFERENCES users (id)
) ENGINE=InnoDB COMMENT='商家认证审核记录';

CREATE TABLE customer_addresses (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  receiver_name VARCHAR(80) NOT NULL,
  receiver_phone VARCHAR(20) NOT NULL,
  province VARCHAR(80) NOT NULL,
  city VARCHAR(80) NOT NULL,
  district VARCHAR(80) NOT NULL,
  detail_address VARCHAR(255) NOT NULL,
  is_default TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted_at DATETIME(3) NULL,
  PRIMARY KEY (id),
  KEY idx_customer_addresses_user (user_id, is_default),
  CONSTRAINT fk_customer_addresses_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB COMMENT='客户收货地址';

CREATE TABLE categories (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  parent_id BIGINT UNSIGNED NULL,
  name VARCHAR(80) NOT NULL,
  code VARCHAR(80) NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_categories_code (code),
  KEY idx_categories_parent (parent_id, sort_order),
  CONSTRAINT fk_categories_parent FOREIGN KEY (parent_id) REFERENCES categories (id)
) ENGINE=InnoDB COMMENT='灯具分类';

CREATE TABLE products (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  category_id BIGINT UNSIGNED NOT NULL,
  created_by_merchant_id BIGINT UNSIGNED NULL,
  name VARCHAR(160) NOT NULL,
  brand VARCHAR(100) NULL,
  style VARCHAR(80) NULL,
  application_space VARCHAR(100) NULL,
  description TEXT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
  version INT UNSIGNED NOT NULL DEFAULT 1,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted_at DATETIME(3) NULL,
  PRIMARY KEY (id),
  KEY idx_products_category_status (category_id, status),
  KEY idx_products_merchant_status (created_by_merchant_id, status),
  KEY idx_products_name (name),
  CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories (id),
  CONSTRAINT fk_products_merchant FOREIGN KEY (created_by_merchant_id) REFERENCES merchant_profiles (id)
) ENGINE=InnoDB COMMENT='灯具商品 SPU';

CREATE TABLE product_skus (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  product_id BIGINT UNSIGNED NOT NULL,
  sku_code VARCHAR(80) NOT NULL,
  color VARCHAR(80) NULL,
  size_spec VARCHAR(120) NULL,
  material VARCHAR(120) NULL,
  power_watt DECIMAL(8,2) NULL,
  color_temperature VARCHAR(60) NULL,
  luminous_flux_lm INT UNSIGNED NULL,
  voltage VARCHAR(60) NULL,
  light_source_type VARCHAR(80) NULL,
  dimming_mode VARCHAR(100) NULL,
  installation_method VARCHAR(100) NULL,
  smart_protocol VARCHAR(100) NULL,
  extra_attributes JSON NULL,
  reference_price DECIMAL(12,2) NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_product_skus_code (sku_code),
  KEY idx_product_skus_product (product_id, status),
  CONSTRAINT fk_product_skus_product FOREIGN KEY (product_id) REFERENCES products (id),
  CONSTRAINT ck_product_skus_reference_price CHECK (reference_price IS NULL OR reference_price >= 0)
) ENGINE=InnoDB COMMENT='商品 SKU';

CREATE TABLE product_images (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  product_id BIGINT UNSIGNED NOT NULL,
  sku_id BIGINT UNSIGNED NULL,
  file_id BIGINT UNSIGNED NOT NULL,
  image_type VARCHAR(20) NOT NULL DEFAULT 'GALLERY',
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_product_images_product (product_id, sku_id, sort_order),
  CONSTRAINT fk_product_images_product FOREIGN KEY (product_id) REFERENCES products (id),
  CONSTRAINT fk_product_images_sku FOREIGN KEY (sku_id) REFERENCES product_skus (id),
  CONSTRAINT fk_product_images_file FOREIGN KEY (file_id) REFERENCES uploaded_files (id)
) ENGINE=InnoDB COMMENT='商品图片';

CREATE TABLE product_audits (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  product_id BIGINT UNSIGNED NOT NULL,
  submitted_version INT UNSIGNED NOT NULL,
  result VARCHAR(20) NOT NULL,
  reason VARCHAR(500) NULL,
  auditor_user_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_product_audits_product (product_id, created_at),
  CONSTRAINT fk_product_audits_product FOREIGN KEY (product_id) REFERENCES products (id),
  CONSTRAINT fk_product_audits_auditor FOREIGN KEY (auditor_user_id) REFERENCES users (id)
) ENGINE=InnoDB COMMENT='商品审核记录';

CREATE TABLE merchant_offers (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id BIGINT UNSIGNED NOT NULL,
  sku_id BIGINT UNSIGNED NOT NULL,
  price DECIMAL(12,2) NOT NULL,
  stock_qty INT UNSIGNED NOT NULL DEFAULT 0,
  unit VARCHAR(20) NOT NULL DEFAULT '件',
  status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
  version INT UNSIGNED NOT NULL DEFAULT 1,
  remark VARCHAR(500) NULL,
  effective_at DATETIME(3) NULL,
  expired_at DATETIME(3) NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_merchant_offers_sku_status_price (sku_id, status, price),
  KEY idx_merchant_offers_merchant_status (merchant_id, status),
  CONSTRAINT fk_merchant_offers_merchant FOREIGN KEY (merchant_id) REFERENCES merchant_profiles (id),
  CONSTRAINT fk_merchant_offers_sku FOREIGN KEY (sku_id) REFERENCES product_skus (id),
  CONSTRAINT ck_merchant_offers_price CHECK (price >= 0)
) ENGINE=InnoDB COMMENT='商家 SKU 报价';

CREATE TABLE offer_audits (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  offer_id BIGINT UNSIGNED NOT NULL,
  submitted_version INT UNSIGNED NOT NULL,
  result VARCHAR(20) NOT NULL,
  reason VARCHAR(500) NULL,
  auditor_user_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_offer_audits_offer (offer_id, created_at),
  CONSTRAINT fk_offer_audits_offer FOREIGN KEY (offer_id) REFERENCES merchant_offers (id),
  CONSTRAINT fk_offer_audits_auditor FOREIGN KEY (auditor_user_id) REFERENCES users (id)
) ENGINE=InnoDB COMMENT='报价审核记录';

CREATE TABLE image_embeddings (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sku_id BIGINT UNSIGNED NOT NULL,
  product_image_id BIGINT UNSIGNED NOT NULL,
  model_version VARCHAR(100) NOT NULL,
  vector_dimension INT UNSIGNED NOT NULL,
  vector_blob LONGBLOB NOT NULL,
  faiss_vector_id BIGINT UNSIGNED NOT NULL,
  image_sha256 CHAR(64) NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_image_embeddings_faiss_id (faiss_vector_id),
  UNIQUE KEY uk_image_embeddings_image_model (product_image_id, model_version),
  KEY idx_image_embeddings_sku_model (sku_id, model_version),
  CONSTRAINT fk_image_embeddings_sku FOREIGN KEY (sku_id) REFERENCES product_skus (id),
  CONSTRAINT fk_image_embeddings_image FOREIGN KEY (product_image_id) REFERENCES product_images (id)
) ENGINE=InnoDB COMMENT='图像特征及向量索引映射';

CREATE TABLE favorites (
  user_id BIGINT UNSIGNED NOT NULL,
  product_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (user_id, product_id),
  CONSTRAINT fk_favorites_user FOREIGN KEY (user_id) REFERENCES users (id),
  CONSTRAINT fk_favorites_product FOREIGN KEY (product_id) REFERENCES products (id)
) ENGINE=InnoDB COMMENT='商品收藏';

CREATE TABLE orders (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_no VARCHAR(40) NOT NULL,
  customer_user_id BIGINT UNSIGNED NOT NULL,
  merchant_id BIGINT UNSIGNED NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'PENDING_CONFIRM',
  fulfillment_type VARCHAR(20) NOT NULL DEFAULT 'DELIVERY',
  receiver_name_snapshot VARCHAR(80) NULL,
  receiver_phone_snapshot VARCHAR(20) NULL,
  address_snapshot VARCHAR(500) NULL,
  total_amount DECIMAL(12,2) NOT NULL,
  remark VARCHAR(500) NULL,
  version INT UNSIGNED NOT NULL DEFAULT 1,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  completed_at DATETIME(3) NULL,
  cancelled_at DATETIME(3) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_orders_order_no (order_no),
  KEY idx_orders_customer_status (customer_user_id, status, created_at),
  KEY idx_orders_merchant_status (merchant_id, status, created_at),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_user_id) REFERENCES users (id),
  CONSTRAINT fk_orders_merchant FOREIGN KEY (merchant_id) REFERENCES merchant_profiles (id),
  CONSTRAINT ck_orders_total CHECK (total_amount >= 0)
) ENGINE=InnoDB COMMENT='订单';

CREATE TABLE order_items (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id BIGINT UNSIGNED NOT NULL,
  sku_id BIGINT UNSIGNED NOT NULL,
  offer_id BIGINT UNSIGNED NOT NULL,
  product_name_snapshot VARCHAR(160) NOT NULL,
  sku_code_snapshot VARCHAR(80) NOT NULL,
  sku_attributes_snapshot JSON NOT NULL,
  image_url_snapshot VARCHAR(500) NULL,
  unit_price_snapshot DECIMAL(12,2) NOT NULL,
  quantity INT UNSIGNED NOT NULL,
  subtotal DECIMAL(12,2) NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_order_items_order (order_id),
  CONSTRAINT fk_order_items_order FOREIGN KEY (order_id) REFERENCES orders (id),
  CONSTRAINT fk_order_items_sku FOREIGN KEY (sku_id) REFERENCES product_skus (id),
  CONSTRAINT fk_order_items_offer FOREIGN KEY (offer_id) REFERENCES merchant_offers (id),
  CONSTRAINT ck_order_items_quantity CHECK (quantity > 0),
  CONSTRAINT ck_order_items_amount CHECK (unit_price_snapshot >= 0 AND subtotal >= 0)
) ENGINE=InnoDB COMMENT='订单明细及交易快照';

CREATE TABLE shipment_records (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id BIGINT UNSIGNED NOT NULL,
  carrier_name VARCHAR(100) NULL,
  tracking_no VARCHAR(100) NULL,
  proof_file_id BIGINT UNSIGNED NULL,
  shipped_at DATETIME(3) NOT NULL,
  created_by_user_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_shipment_records_order (order_id, shipped_at),
  CONSTRAINT fk_shipment_records_order FOREIGN KEY (order_id) REFERENCES orders (id),
  CONSTRAINT fk_shipment_records_proof FOREIGN KEY (proof_file_id) REFERENCES uploaded_files (id),
  CONSTRAINT fk_shipment_records_creator FOREIGN KEY (created_by_user_id) REFERENCES users (id)
) ENGINE=InnoDB COMMENT='订单发货记录';

CREATE TABLE reviews (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_item_id BIGINT UNSIGNED NOT NULL,
  customer_user_id BIGINT UNSIGNED NOT NULL,
  rating TINYINT UNSIGNED NOT NULL,
  content VARCHAR(2000) NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'VISIBLE',
  merchant_reply VARCHAR(1000) NULL,
  replied_at DATETIME(3) NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_reviews_order_item (order_item_id),
  KEY idx_reviews_customer (customer_user_id, created_at),
  KEY idx_reviews_status (status, created_at),
  CONSTRAINT fk_reviews_order_item FOREIGN KEY (order_item_id) REFERENCES order_items (id),
  CONSTRAINT fk_reviews_customer FOREIGN KEY (customer_user_id) REFERENCES users (id),
  CONSTRAINT ck_reviews_rating CHECK (rating BETWEEN 1 AND 5)
) ENGINE=InnoDB COMMENT='订单评价';

CREATE TABLE review_images (
  review_id BIGINT UNSIGNED NOT NULL,
  file_id BIGINT UNSIGNED NOT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  PRIMARY KEY (review_id, file_id),
  CONSTRAINT fk_review_images_review FOREIGN KEY (review_id) REFERENCES reviews (id),
  CONSTRAINT fk_review_images_file FOREIGN KEY (file_id) REFERENCES uploaded_files (id)
) ENGINE=InnoDB COMMENT='评价图片';

CREATE TABLE notifications (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  notification_type VARCHAR(40) NOT NULL,
  title VARCHAR(160) NOT NULL,
  content VARCHAR(1000) NOT NULL,
  business_type VARCHAR(40) NULL,
  business_id BIGINT UNSIGNED NULL,
  read_at DATETIME(3) NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_notifications_user_read (user_id, read_at, created_at),
  CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB COMMENT='站内通知';

CREATE TABLE operation_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NULL,
  action VARCHAR(80) NOT NULL,
  object_type VARCHAR(60) NOT NULL,
  object_id BIGINT UNSIGNED NULL,
  result VARCHAR(20) NOT NULL,
  request_id VARCHAR(64) NULL,
  ip_address VARCHAR(64) NULL,
  detail_json JSON NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_operation_logs_object (object_type, object_id, created_at),
  KEY idx_operation_logs_user (user_id, created_at),
  KEY idx_operation_logs_request (request_id),
  CONSTRAINT fk_operation_logs_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE=InnoDB COMMENT='关键操作审计日志';

INSERT INTO roles (code, name) VALUES
  ('CUSTOMER', '客户'),
  ('MERCHANT', '商家'),
  ('ADMIN', '管理员')
ON DUPLICATE KEY UPDATE name = VALUES(name);

